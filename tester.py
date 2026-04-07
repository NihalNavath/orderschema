import os

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d != "__pycache__"]

    for f in files:
        path = os.path.join(root, f)

        try:
            with open(path, "rb") as file:
                content = file.read()

            content.decode("utf-8")  # strict decode

        except Exception as e:
            print(f"\n❌ Problem file: {path}")
            print(e)
            break