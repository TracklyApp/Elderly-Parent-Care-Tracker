# Kindred - clean source package

This package contains the local application source and the English user manual.
Extract the ZIP, then upload its contents to your Git repository. Keep index.html
at the repository root. Do not upload the ZIP itself as the website source.

## Included

- HTML, CSS and JavaScript application files, icons and the offline manifest.
- Python family server, recovery tool and dependency requirements.
- Windows launchers and dependency installer.
- User Guide in the application and output/pdf/Kindred-User-Guide.pdf.
- Manual content and the optional PDF build script.

## Excluded

Personal records, browser profiles, accounts, uploaded documents, databases,
backups, encryption keys, temporary files, screenshots, development tests,
downloaded Python runtime and installed dependency libraries are not included.

Do not add your local data/, .runtime/, vendor/, tmp/ or release/ folders later.
The included .gitignore also excludes common database and secret files.

## Run a fresh copy

1. Install Python 3.10 or newer on the computer, with the Python launcher or
   python command available.
2. Run Install dependencies.cmd. It installs the required libraries in vendor/.
3. Run Start Kindred.cmd and keep the server window open.
4. Open http://localhost:8877 in Chrome or Edge on that computer.

The application can also open as index.html for local browser records; server
accounts and server document features require the running Python server.
The clean Git source package does not include the bundled Python runtime that
may exist in the original development folder. Uploading source to Git does not
itself make the Python server run online or install the application on a phone.

## Activation and the Etsy PDF

No product activation code, license-key validation or Etsy activation PDF is
included. Authentication, caregiver invitation codes and authenticator recovery
codes are account-security features, not product activation codes.

A code placed only in a separate PDF does not restrict application access,
because this application does not validate purchase or activation codes.
Keep the separate Etsy delivery PDF outside the source package.

## Manual

Use User Guide in the application or Open User Manual.cmd. The same guide is
available at output/pdf/Kindred-User-Guide.pdf. This guide contains no real
personal records. The fictional demo has 20 records in total.

Optional manual build dependencies: reportlab, pypdf and pymupdf. build_manual.py
uses Windows Segoe UI fonts and looks for these dependencies in data/pdf-tools/.
They are only needed to regenerate the manual, not to run the application.

## Repository visibility

Choose a private repository if you do not intend to publish the source code.
This package does not choose a software license or publish anything for you.
