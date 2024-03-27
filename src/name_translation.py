from pytrovich.detector import PetrovichGenderDetector
from pytrovich.enums import NamePart, Gender, Case
from pytrovich.maker import PetrovichDeclinationMaker

maker = PetrovichDeclinationMaker()
detector = PetrovichGenderDetector()


def name_to_gender(fio: str) -> Gender:
    lastname, firstname, middlename = tuple(fio.split())
    return detector.detect(
        firstname=firstname, middlename=middlename, lastname=lastname
    )


def fio_to_accusative(fio: str) -> str:
    lastname, firstname, middlename = tuple(fio.split())

    gender = name_to_gender(fio)
    cased_lname = maker.make(NamePart.LASTNAME, gender, Case.ACCUSATIVE, lastname)
    cased_fname = maker.make(NamePart.FIRSTNAME, gender, Case.ACCUSATIVE, firstname)
    cased_mname = maker.make(NamePart.MIDDLENAME, gender, Case.ACCUSATIVE, middlename)

    return f"{cased_lname} {cased_fname} {cased_mname}"
