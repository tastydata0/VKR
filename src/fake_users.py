import random
from faker import Faker
from src.models import *
import os
import src.database as database

fake = Faker("ru_RU")


def random_document(subfolder) -> Document:
    return Document(
        filename=os.path.join(
            "data/fake_documents/",
            subfolder,
            random.choice(os.listdir("data/fake_documents/" + subfolder)),
        ),
        timestamp=datetime.now(),
        encryptionKey="",
        encryptionVersion=0,
    )


def random_user() -> User:
    states = ("filling_info", "filling_docs", "waiting_confirmation", "approved")
    state = random.choice(states)
    user = User(
        email=fake.email(),
        parentFullName=fake.name(),
        parentAddress=fake.address(),
        birthPlace=fake.address(),
        phone=f"+{random.randint(int(1e10), int(1e11 - 1))}",
        parentPhone=f"+{random.randint(int(1e10), int(1e11 - 1))}",
        fullName=fake.name(),
        parentEmail=fake.email(),
        school=fake.profile()["company"],
        schoolClass=random.randint(5, 11),
        birthDate=fake.profile()["birthdate"].strftime("%d.%m.%Y"),
    )
    user.application.status = state

    user.application.lastRejectionReason = fake.text()

    if states.index(state) >= states.index("filling_docs"):
        user.application.selectedProgram = random.choice(
            [
                p.confirmed[0].realizations[0].id
                for p in database.load_relevant_programs()
            ]
        )

    if states.index(state) > states.index("filling_docs"):
        user.application.documents = ApplicationDocuments(
            applicationFiles=[random_document("pictures")],
            consentFiles=[random_document("pictures")],
            parentPassportFiles=[random_document("pictures")],
            childPassportFiles=[random_document("pictures")],
            parentSnilsFiles=[random_document("pictures")],
            childSnilsFiles=[random_document("pictures")],
            mergedPdf=random_document("pdf"),
        )

    return user


for i in range(100):
    try:
        database.insert_fake_user(random_user())
    except:
        pass
# print(random_user())
