# Publishing Bank Orderly

1. Create a backup of your original V3 folder. Never upload its `data/` directory.
2. Download and extract this prepared ZIP.
3. On GitHub, open `https://github.com/kjones0401/Bank-Orderly`.
4. Choose **Add file → Upload files** and upload the **contents** of the extracted folder (not the ZIP itself).
5. Make sure `.gitignore`, README.md, Python files, `templates/` and `static/` are included.
6. Confirm there is **no** `data/`, `*.sqlite`, `*.jsonl`, migration export, backup or credential file in the GitHub commit preview.
7. Commit with message `Publish Bank Orderly v3.1 source and documentation`.
8. Verify the README shows on the repository homepage and the test scripts are available.

**Reminder:** `.gitignore` does not protect files uploaded directly through GitHub's browser uploader; visually inspect the files before committing.

The `docs/test_results*.txt` are historical outputs included from your uploaded project. They are not fresh test runs performed during packaging.
