"""Include the installed Mac dependencies' actual license files and versions."""
import importlib.metadata as metadata
from pathlib import Path
import shutil
import sys

bundle = Path(sys.argv[1])
licenses = bundle / "licenses"
licenses.mkdir(exist_ok=True)
rows = []
for dist in metadata.distributions():
    name = dist.metadata["Name"]
    if name.lower() not in {"bleak", "typing_extensions", "pyinstaller"} and not name.lower().startswith("pyobjc"):
        continue
    files = [f for f in dist.files or [] if "license" in str(f).lower() or "copying" in str(f).lower()]
    if not files:
        # PyObjC wheels omit the upstream license file; ship our upstream copy.
        if name.lower().startswith("pyobjc"):
            assert (licenses / "PyObjC-MIT.txt").is_file()
            rows.append(f"| {name} | {dist.version} | [MIT](licenses/PyObjC-MIT.txt) |")
            continue
        raise RuntimeError(f"Missing license files for {name}")
    for i, file in enumerate(files):
        target = f"{name}-{i}-{file.name}"
        shutil.copyfile(dist.locate_file(file), licenses / target)
        rows.append(f"| {name} | {dist.version} | [License](licenses/{target}) |")
assert any("bleak" in row.lower() for row in rows)
text = "# macOS third-party notices\n\nPython " + sys.version.split()[0]
text += "; Python and bundled-library notices: [LICENSE](licenses/Python-LICENSE.txt).\n\n"
text += "| Component | Installed version | Notice |\n| --- | --- | --- |\n" + "\n".join(rows) + "\n"
text += "\nPyObjC bundled libffi notice: [MIT](licenses/libffi-MIT.txt).\n"
(bundle / "THIRD_PARTY_NOTICES.md").write_text(text, encoding="utf-8")
