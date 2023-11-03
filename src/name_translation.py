from petrovich.main import Petrovich
from petrovich.enums import Case, Gender
import pymorphy3

morph = pymorphy3.MorphAnalyzer()
p = Petrovich()


def name_to_gender(name: str) -> Gender:
    parsed_word = morph.parse(name)[0]
    return Gender.MALE if parsed_word.tag.gender == "masc" else Gender.FEMALE


def fio_to_genitive(fio: str) -> str:
    lastname, firstname, middlename = tuple(fio.split())

    gender = name_to_gender(middlename)
    cased_lname = p.lastname(lastname, Case.GENITIVE, gender)
    cased_fname = p.firstname(firstname, Case.GENITIVE, gender)
    cased_mname = p.middlename(middlename, Case.GENITIVE, gender)

    return f"{cased_lname} {cased_fname} {cased_mname}"

