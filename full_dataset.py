import argparse
import json
import unicodedata
from pathlib import Path
from urllib.request import urlopen

import pandas as pd


DATA = Path(__file__).resolve().parent / "data"
ATLAS_FILE = DATA / "brazil.xlsx"

NOMINAL_DAMAGE = "Total Damage ('000 US$)"
ADJUSTED_DAMAGE = "Total Damage, Adjusted ('000 US$)"

# True: Atlas zero damage becomes missing and can be imputed by the scorer.
# False: Atlas zero damage stays zero.
ZERO_DAMAGE_IS_MISSING = True

STATES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá",
    "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
    "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}


def clean_text(value):
    """Normalize text so accents, capitalization, and spacing do not affect matches."""
    if pd.isna(value):
        return ""

    text = unicodedata.normalize("NFKD", str(value).casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.split())


def state_key(value):
    """Give a state abbreviation and its full name the same matching key."""
    name = STATES.get(str(value).strip().upper(), value)
    return clean_text(name)


def required_brazil_locations(nodes, edges):
    """Collect unique Brazilian city-state pairs from nodes and route stops."""
    locations = set()

    for _, node in nodes.iterrows():
        if clean_text(node["country"]) in {"brazil", "brasil"}:
            locations.add((clean_text(node["city"]), state_key(node["region"])))

    for route in edges["cities_along_route"]:
        for stop in json.loads(route):
            parts = stop.rsplit(",", 2)
            if len(parts) != 3:
                continue

            city, state, country = parts
            if clean_text(country) in {"brazil", "brasil"}:
                locations.add((clean_text(city), state_key(state)))

    return locations


def load_atlas(path):
    """Read original BRL amounts, before any Brazilian inflation adjustment."""
    path = Path(path)

    if path.suffix.lower() == ".csv":
        # Use only an original-value CSV such as brazil_original.csv.
        # The official corrected-value CSV is already inflation-adjusted.
        return pd.read_csv(path, sep=";", low_memory=False)

    with pd.ExcelFile(path) as workbook:
        original_sheet = next(
            name for name in workbook.sheet_names
            if "origin" in clean_text(name)
        )
        return pd.read_excel(workbook, sheet_name=original_sheet)


def filter_atlas(atlas, nodes, edges):
    """Keep only Atlas records from municipalities used by the project."""
    required = required_brazil_locations(nodes, edges)
    cities = atlas["Nome_Municipio"].map(clean_text)
    states = atlas["Sigla_UF"].map(state_key)

    keep = [(city, state) in required for city, state in zip(cities, states)]
    return atlas.loc[keep].copy()


def load_exchange_rates():
    """Read annual BRL per USD rates locally, or download them into memory."""
    rates_path = DATA / "exchange_rates.csv"

    if rates_path.exists():
        return pd.read_csv(rates_path)

    url = (
        "https://api.bcb.gov.br/dados/serie/"
        "bcdata.sgs.3694/dados?formato=json"
    )

    with urlopen(url, timeout=60) as response:
        records = pd.DataFrame(json.load(response))

    return pd.DataFrame({
        "year": pd.to_datetime(records["data"], format="%d/%m/%Y").dt.year,
        "brl_per_usd": pd.to_numeric(
            records["valor"].astype(str).str.replace(",", ".", regex=False)
        ),
    })


def disaster_type(code):
    """Map a Brazilian COBRADE code to the project's disaster categories."""
    code = str(code)

    if code.startswith("111"):
        return "Earthquake"
    if code.startswith("112"):
        return "Volcanic activity"
    if code.startswith("113"):
        # Preserve the project's existing mass-movement mapping.
        return "Mass movement (wet)" if code == "11321" else "Mass movement (dry)"
    if code.startswith("12"):
        return "Flood"
    if code.startswith(("1311", "132")):
        return "Storm"
    if code.startswith(("1312", "133")):
        return "Extreme temperature"
    if code.startswith(("1411", "1412")):
        return "Drought"
    if code.startswith("1413"):
        return "Wildfire"
    if code.startswith("151"):
        return "Epidemic"
    if code.startswith("152"):
        return "Infestation"

    return pd.NA


def translate_atlas(atlas, emdat, rates):
    """Convert the filtered Atlas records into EM-DAT-compatible columns."""
    atlas = atlas.copy()

    # Accept Excel dates, ISO dates, and Brazilian day/month/year dates.
    date_text = atlas["Data_Evento"].astype("string")
    is_iso = date_text.str.match(r"^\d{4}-", na=False)

    dates = pd.to_datetime(
        date_text.where(is_iso), format="ISO8601", errors="coerce"
    )
    dates = dates.fillna(
        pd.to_datetime(
            date_text.where(~is_iso), format="%d/%m/%Y", errors="coerce"
        )
    )

    if dates.isna().any():
        raise ValueError("Atlas contains missing or invalid event dates.")

    atlas = atlas.loc[dates.dt.year.between(2000, 2025)].copy()
    codes = pd.to_numeric(atlas["Cod_Cobrade"]).astype(int).astype(str)
    types = codes.map(disaster_type)

    # Only supported disaster types enter the combined file.
    atlas = atlas.loc[types.notna()].copy()
    dates = dates.loc[atlas.index]

    impact_columns = [
        "DH_MORTOS",
        "DH_DESAPARECIDOS",
        "DH_FERIDOS",
        "DH_ENFERMOS",
        "DH_DESABRIGADOS",
        "DH_DESALOJADOS",
        "DH_AFETADOS_SECA_ESTIAGEM",
        "DH_total_danos_humanos_diretos",
        "DH_OUTROS AFETADOS",
        "DM_total_danos_materiais",
    ]
    atlas[impact_columns] = atlas[impact_columns].apply(
        pd.to_numeric, errors="coerce"
    )

    result = pd.DataFrame(index=atlas.index)

    # Each Atlas protocol represents one municipal disaster report.
    result["Source"] = "Atlas"
    result["Source Record ID"] = atlas["Protocolo_S2iD"]
    result["Event ID"] = "ATLAS-" + atlas["Protocolo_S2iD"].astype("string")
    result["DisNo."] = result["Event ID"] + "-BRA"

    result["Disaster Group"] = "Natural"
    result["Disaster Type"] = types.loc[atlas.index]
    result["Source Disaster Type"] = atlas["descricao_tipologia"]
    result["COBRADE"] = codes.loc[atlas.index]

    result["Country"] = "Brazil"
    result["ISO"] = "BRA"
    result["Region"] = "Americas"
    result["Subregion"] = "South America"
    result["Municipality"] = atlas["Nome_Municipio"]
    result["State"] = atlas["Sigla_UF"].map(STATES)
    result["Municipality Key"] = atlas["Nome_Municipio"].map(clean_text)
    result["State Key"] = atlas["Sigla_UF"].map(state_key)
    result["Location"] = result["Municipality"] + ", " + result["State"]

    result["Start Year"] = dates.dt.year.astype(int)
    result["Start Month"] = dates.dt.month.astype(int)
    result["Start Day"] = dates.dt.day.astype(int)
    result["Total Deaths"] = atlas["DH_MORTOS"]

    # Keep the existing affected-person proxy to avoid adding overlapping totals.
    direct_nonfatal = (
        atlas["DH_total_danos_humanos_diretos"]
        - atlas["DH_MORTOS"].fillna(0)
        - atlas["DH_DESAPARECIDOS"].fillna(0)
    ).clip(lower=0)

    affected_columns = [
        "DH_FERIDOS",
        "DH_ENFERMOS",
        "DH_DESABRIGADOS",
        "DH_DESALOJADOS",
        "DH_AFETADOS_SECA_ESTIAGEM",
        "DH_OUTROS AFETADOS",
    ]
    result["Total Affected"] = (
        atlas[affected_columns]
        .assign(direct_nonfatal=direct_nonfatal)
        .max(axis=1)
    )
    result["Affected Definition"] = "Maximum reported nonfatal total/category (proxy)"

    # Keep the reported BRL amount even when zero is treated as missing for scoring.
    damage_brl = atlas["DM_total_danos_materiais"]
    result["Source Material Damage (BRL)"] = damage_brl

    if ZERO_DAMAGE_IS_MISSING:
        damage_brl = damage_brl.mask(damage_brl.eq(0))

    rate_by_year = rates.set_index("year")["brl_per_usd"]
    cpi_by_year = emdat.groupby("Start Year")["CPI"].median()

    result["BRL per USD"] = result["Start Year"].map(rate_by_year)
    result["CPI"] = result["Start Year"].map(cpi_by_year)

    if result[["BRL per USD", "CPI"]].isna().any().any():
        raise ValueError("An Atlas year is missing its exchange rate or EM-DAT CPI.")

    # Original BRL -> thousands of nominal USD -> thousands of adjusted USD.
    result[NOMINAL_DAMAGE] = damage_brl / result["BRL per USD"] / 1000
    result[ADJUSTED_DAMAGE] = result[NOMINAL_DAMAGE] * 100 / result["CPI"]
    result["Damage Definition"] = "Atlas total material damage; excludes economic losses"

    return result.reset_index(drop=True)


def prepare_combined(atlas_path=ATLAS_FILE):
    """Build the combined dataset and write a single output CSV."""
    nodes = pd.read_csv(DATA / "nodes.csv")
    edges = pd.read_csv(DATA / "edges.csv")

    # Filter Atlas to the route locations before translating or converting impacts.
    atlas = filter_atlas(load_atlas(atlas_path), nodes, edges)

    emdat = pd.read_excel(DATA / "emdat.xlsx")
    brazil = translate_atlas(atlas, emdat, load_exchange_rates())

    if brazil["DisNo."].isna().any() or brazil["DisNo."].duplicated().any():
        raise ValueError("Atlas contains missing or duplicate record IDs.")

    # Keep EM-DAT for every country except Brazil.
    is_brazil = emdat["Country"].map(clean_text).isin(["brazil", "brasil"])
    emdat = emdat.loc[~is_brazil].copy()
    emdat["Source"] = "EM-DAT"
    emdat["Event ID"] = (
        emdat["DisNo."]
        .astype("string")
        .str.replace(r"-[A-Z]{3}$", "", regex=True)
    )
    emdat = emdat.drop(columns=["Continent"], errors="ignore")

    combined = pd.concat([emdat, brazil], ignore_index=True, sort=False)

    output = DATA / "combined_disasters.csv"
    combined.to_csv(output, index=False)

    print(f"Saved {len(combined):,} records to {output}")
    print(f"EM-DAT: {len(emdat):,} | Atlas Brazil: {len(brazil):,}")

    return combined


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", type=Path, default=ATLAS_FILE)
    args = parser.parse_args()

    prepare_combined(args.atlas)