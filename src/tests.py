import unittest
from returns.result import Success, Failure
from returns.pipeline import is_successful
import sys

sys.path.insert(0, "./src")
import name_translation
from models import *


class TestNameTranslation(unittest.TestCase):
    def test_normal_fio(self):
        self.assertEqual(
            name_translation.fio_to_accusative("Иванов Иван Иванович"),
            Success("Иванова Ивана Ивановича"),
        )

    def test_wrong_structure_fio(self):
        self.assertFalse(
            is_successful(name_translation.fio_to_accusative("Иванов Иван"))
        )


class TestEncryption(unittest.TestCase):
    def test_save_load_encryption_version_1(self):
        doc = Document.save_file("/tmp/test_doc_0.bin", b"SFEDU")
        self.assertEqual(doc.read_file(), b"SFEDU")

    def test_save_load_encryption_version_0(self):
        with open("/tmp/plaintext.txt", "wb") as f:
            f.write(b"SFEDU")
        doc = Document(filename="/tmp/plaintext.txt", encryptionVersion=0)
        self.assertEqual(doc.read_file(), b"SFEDU")


class TestProgramsConfirmation(unittest.TestCase):
    def test_confirm_program_by_datetime(self):
        p = Program(baseId="test", brief="Brief", infoHtml="", difficulty=1, iconUrl="")
        confirmed = ProgramConfirmedNoId(
            formalName="Formal",
            cost=12345,
            hoursAud=72,
            hoursHome=36,
            confirmDate=datetime(2024, 4, 12),
        )

        p.add_confirmed_program(confirmed)

        self.assertEqual(
            p.confirmed[0], ProgramConfirmed(id="test-2024-04-12", **confirmed)
        )

    def test_confirm_program_by_string_date(self):
        p = Program(baseId="test", brief="Brief", infoHtml="", difficulty=1, iconUrl="")
        confirmed = ProgramConfirmedNoId(
            formalName="Formal",
            cost=12345,
            hoursAud=72,
            hoursHome=36,
            confirmDate="12.04.2024",
        )

        p.add_confirmed_program(confirmed)

        self.assertEqual(
            p.relevant_confirmed(), ProgramConfirmed(id="test-2024-04-12", **confirmed)
        )

    def test_realize_program_by_datetime(self):
        p = Program(baseId="test", brief="Brief", infoHtml="", difficulty=1, iconUrl="")
        confirmed = ProgramConfirmedNoId(
            formalName="Formal",
            cost=12345,
            hoursAud=72,
            hoursHome=36,
            confirmDate=datetime(2024, 4, 12),
        )

        p.add_confirmed_program(confirmed)

        realizeOld = ProgramRealizationNoId(
            realizationDate=datetime(2024, 4, 12),
            finishDate=datetime(2024, 4, 15),
        )
        realizeMid = ProgramRealizationNoId(
            realizationDate=datetime(2024, 4, 13),
            finishDate=datetime(2024, 4, 16),
        )
        realizeNew = ProgramRealizationNoId(
            realizationDate=datetime(2024, 4, 14),
            finishDate=datetime(2024, 4, 17),
        )

        p.add_program_realization(realizeOld)
        p.add_program_realization(realizeNew)
        p.add_program_realization(realizeMid)

        self.assertEqual(
            p.relevant_realization(),
            ProgramRealization(id="test-2024-04-12-rel-2024-04-12", **realizeNew),
        )

    def test_realize_program_by_string_date(self):
        p = Program(baseId="test", brief="Brief", infoHtml="", difficulty=1, iconUrl="")
        confirmed = ProgramConfirmedNoId(
            formalName="Formal",
            cost=12345,
            hoursAud=72,
            hoursHome=36,
            confirmDate="12.04.2024",
        )

        p.add_confirmed_program(confirmed)

        realizeOld = ProgramRealizationNoId(
            realizationDate="12.04.2024",
            finishDate="15.04.2024",
        )
        realizeMid = ProgramRealizationNoId(
            realizationDate="13.04.2024",
            finishDate="16.04.2024",
        )
        realizeNew = ProgramRealizationNoId(
            realizationDate="14.04.2024",
            finishDate="17.04.2024",
        )

        p.add_program_realization(realizeOld)
        p.add_program_realization(realizeNew)
        p.add_program_realization(realizeMid)

        self.assertEqual(
            p.relevant_realization(),
            ProgramRealization(id="test-2024-04-12-rel-2024-04-12", **realizeNew),
        )


if __name__ == "__main__":
    unittest.main()
