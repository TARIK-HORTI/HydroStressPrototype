"""Contributions de données (sans réseau : stockage local et faux bucket GCS)."""
import json
from datetime import datetime, timezone

import pytest

import contrib
from contrib import Contribution, GCSStorage, GitHubStorage, LocalStorage, submit


def make(**kw):
    args = dict(
        contact={"name": "Ahmed", "phone": "0612345678", "email": "", "organisation": ""},
        farm={"name": "Bloc 4", "latitude": 31.88, "longitude": -4.15, "crop": "amandier"},
        consent=True,
        registers=[("irrigation 2021-2022.xlsx", b"PK\x03\x04data")],
    )
    args.update(kw)
    return Contribution(**args)


def test_complete_contribution_has_no_errors():
    assert make().errors() == []


@pytest.mark.parametrize("kw,needle", [
    ({"consent": False}, "accord"),
    ({"contact": {"name": "", "phone": "06", "email": ""}}, "nom"),
    ({"contact": {"name": "A", "phone": "", "email": ""}}, "téléphone"),
    ({"contact": {"name": "A", "phone": "", "email": "pas-un-mail"}}, "e-mail"),
    ({"registers": [], "other_files": []}, "fichier"),
    ({"registers": [("f.csv", b"x")] * 31}, "maximum"),
])
def test_incomplete_contribution_is_refused(kw, needle):
    errs = make(**kw).errors()
    assert errs and any(needle in e for e in errs)
    with pytest.raises(ValueError):
        submit(make(**kw), LocalStorage("unused"))


def test_submit_local_writes_manifest_and_files(tmp_path):
    c = make(other_files=[("../../etc/passwd", b"x"), ("photo stress.jpg", b"jpg")], comment="  Panne en août  ")
    now = datetime(2026, 11, 20, 9, 30, tzinfo=timezone.utc)
    ref = submit(c, LocalStorage(str(tmp_path)), now=now)
    folders = list(tmp_path.iterdir())
    assert len(folders) == 1 and folders[0].name.startswith("20261120-093000_bloc-4_") and folders[0].name.endswith(ref)
    manifest = json.loads((folders[0] / "contribution.json").read_text(encoding="utf-8"))
    assert manifest["reference"] == ref and manifest["consent"]["accepted"] is True
    assert manifest["comment"] == "Panne en août"
    files = sorted(p.relative_to(folders[0] / "fichiers").as_posix() for p in (folders[0] / "fichiers").rglob("*") if p.is_file())
    # Les noms de fichiers ne peuvent pas sortir du dossier de la contribution
    assert files == ["autres/passwd", "autres/photo stress.jpg", "registres/irrigation 2021-2022.xlsx"]


def test_duplicate_file_names_are_kept(tmp_path):
    c = make(registers=[("r.xlsx", b"1"), ("r.xlsx", b"2")])
    submit(c, LocalStorage(str(tmp_path)))
    folder = next(tmp_path.iterdir())
    assert sorted(p.read_bytes() for p in (folder / "fichiers" / "registres").iterdir()) == [b"1", b"2"]


def test_gcs_storage_uploads_under_contributions_prefix():
    uploaded = {}

    class Blob:
        def __init__(self, name):
            self.name = name

        def upload_from_string(self, data, content_type=None):
            uploaded[self.name] = (data, content_type)

    class Bucket:
        def blob(self, name):
            return Blob(name)

    class Client:
        def bucket(self, name):
            assert name == "hydrostress-contrib"
            return Bucket()

    ref = submit(make(), GCSStorage("hydrostress-contrib", client=Client()))
    names = sorted(uploaded)
    assert all(n.startswith("contributions/") for n in names)
    assert any(n.endswith(f"{ref}/contribution.json") for n in names)
    xlsx = next(v for n, v in uploaded.items() if n.endswith(".xlsx"))
    assert xlsx[1].startswith("application/vnd.openxmlformats")


def test_storage_is_local_without_bucket(monkeypatch):
    monkeypatch.delenv("CONTRIB_BUCKET", raising=False)
    monkeypatch.setattr(contrib, "_setting", lambda name: "")
    assert isinstance(contrib.get_storage(), LocalStorage)


def test_summary_is_none_when_registers_unreadable():
    assert contrib.summarize_registers([("x.xlsx", b"not an excel file")], 10) is None
    assert contrib.summarize_registers([("x.xlsx", b"PK")], None) is None


class FakeSession:
    def __init__(self, status=201):
        self.headers, self.calls, self.status = {}, [], status

    def put(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        status = self.status

        class R:
            status_code = status

            @staticmethod
            def json():
                return {"message": "Bad credentials"}
        return R()


def test_github_storage_puts_files_in_private_repo():
    import base64

    s = FakeSession()
    ref = submit(make(), GitHubStorage("TARIK-HORTI/hydrostress-contributions", "secret", session=s))
    assert s.headers["Authorization"] == "Bearer secret"
    urls = [u for u, _ in s.calls]
    assert all(u.startswith("https://api.github.com/repos/TARIK-HORTI/hydrostress-contributions/contents/contributions/")
               for u in urls)
    assert any(u.endswith(f"{ref}/contribution.json") for u in urls)
    xlsx = next(body for u, body in s.calls if u.endswith(".xlsx"))
    assert base64.b64decode(xlsx["content"]) == b"PK\x03\x04data" and xlsx["branch"] == "main"
    assert any("irrigation%202021-2022.xlsx" in u for u in urls)


def test_github_storage_reports_refusal():
    with pytest.raises(RuntimeError, match="401"):
        submit(make(), GitHubStorage("o/r", "bad", session=FakeSession(status=401)))


def test_github_repo_must_be_owner_slash_name():
    with pytest.raises(ValueError):
        GitHubStorage("pas un depot", "t", session=FakeSession())


def test_storage_prefers_github_when_configured(monkeypatch):
    values = {"CONTRIB_GITHUB_REPO": "o/r", "CONTRIB_GITHUB_TOKEN": "t"}
    monkeypatch.setattr(contrib, "_setting", lambda name: values.get(name, ""))
    assert isinstance(contrib.get_storage(), GitHubStorage)


def test_settings_found_inside_a_secrets_section():
    secrets = {"gcp_service_account": {"type": "service_account", "CONTRIB_GITHUB_REPO": "o/r"},
               "CONTRIB_GITHUB_TOKEN": "t"}
    assert contrib._find_setting(secrets, "CONTRIB_GITHUB_REPO") == "o/r"
    assert contrib._find_setting(secrets, "CONTRIB_GITHUB_TOKEN") == "t"
    assert contrib._find_setting(secrets, "ABSENT") == ""
