import os
import zipfile
import sys

def make_zip(source_dir, output_zip):
    if os.path.exists(output_zip):
        os.remove(output_zip)
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir).replace('\\', '/')
                zipf.write(file_path, arcname)
    print(f"Successfully packaged {output_zip} ({os.path.getsize(output_zip)} bytes)")

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else 'Louders-Official-Encrypted'
    out = sys.argv[2] if len(sys.argv) > 2 else 'Louders-Official-Encrypted.zip'
    make_zip(src, out)
