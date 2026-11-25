import pandas as pd
import pytest

from ev_gap.keys import apply_merges, is_city_name, map_register_names, normalise_name


def key_of(mapping: pd.DataFrame, name: str) -> str:
    return mapping.set_index("kreis_name").loc[name, "key"]


def test_normalise_name_ignores_prefix_suffix_brackets_and_spaces():
    assert normalise_name("Landkreis Mühldorf a. Inn") == normalise_name("Mühldorf a.Inn")
    assert normalise_name("Kreisfreie Stadt Oldenburg (Oldb)") == normalise_name("Oldenburg (Oldenburg), Stadt")
    assert normalise_name("Kreis Städteregion Aachen") == normalise_name("Städteregion Aachen")


def test_is_city_name():
    assert is_city_name("Kreisfreie Stadt Passau")
    assert is_city_name("Stadtkreis Stuttgart")
    assert not is_city_name("Landkreis Passau")


def test_city_and_landkreis_with_the_same_name_get_different_keys(destatis):
    mapping = map_register_names(["Kreisfreie Stadt Passau", "Landkreis Passau"], destatis)
    assert key_of(mapping, "Kreisfreie Stadt Passau") == "09262"
    assert key_of(mapping, "Landkreis Passau") == "09263"
    mapping = map_register_names(["Kreisfreie Stadt Oldenburg (Oldb)", "Landkreis Oldenburg"], destatis)
    assert key_of(mapping, "Kreisfreie Stadt Oldenburg (Oldb)") == "03403"
    assert key_of(mapping, "Landkreis Oldenburg") == "03458"


def test_hanau_is_mapped_by_the_manual_rule(destatis):
    mapping = map_register_names(["Kreisfreie Stadt Hanau"], destatis)
    assert key_of(mapping, "Kreisfreie Stadt Hanau") == "06435"


def test_unknown_name_raises(destatis):
    with pytest.raises(ValueError, match="Atlantis"):
        map_register_names(["Landkreis Atlantis"], destatis)


def test_ambiguous_destatis_names_raise(destatis):
    twice = pd.concat([destatis, destatis.iloc[[0]].assign(key="99999")])
    with pytest.raises(ValueError, match="not unique"):
        map_register_names(["Kreisfreie Stadt Flensburg"], twice)


def test_apply_merges():
    merged = apply_merges(pd.Series(["06415", "07235", "01001"]))
    assert merged.tolist() == ["06435", "07211", "01001"]


def test_eisenach_of_the_year_2021_is_merged_into_wartburgkreis():
    assert apply_merges(pd.Series(["16056", "16063"])).tolist() == ["16063", "16063"]
