"""Test files import the shared fixtures under two spellings: 42 use
`from conftest import ...`, 107 use `from tests.conftest import ...`. Python
loaded those as two module objects, each with its own next_test_year()
counter starting at 5000, so files using different spellings handed out the
same "unique" year and collided with 409 planning_year_already_exists
(observed 2026-10-09: rules file before year-linkage file). Session-unique
helpers only work if there is one module.
"""


def test_conftest_is_one_module_under_both_import_spellings():
    import conftest as bare
    import tests.conftest as package
    assert bare is package


def test_next_test_year_is_unique_across_both_import_spellings():
    from conftest import next_test_year as bare
    from tests.conftest import next_test_year as package
    years = [bare(), package(), bare(), package()]
    assert len(set(years)) == len(years), years
