# SmartyBee - How to Run

This is a **Python Flask** web application, not a Node.js app. Follow these steps to run it.

## Prerequisites
- Python 3.8 or higher installed.
- MySQL Server (Optional for Demo Mode, Required for full features).

## Quick Start (Terminal)

1. **Install Dependencies**:
   Open your terminal in this folder and run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**:
   ```bash
   python app.py
   ```

3. **Open in Browser**:
   Go to: [http://localhost:5000](http://localhost:5000)

## Database Setup (Full Mode)
To enable saving progress and custom templates:
1. Make sure MySQL is running.
2. Edit `config.py` with your database password.
3. Run the schema script to create tables:
   You can copy the contents of `schema.sql` and run them in your MySQL Workbench or command line.

## Troubleshooting
- If you see `ModuleNotFoundError`, make sure you ran `pip install -r requirements.txt`.
- if `python` is not recognized, try `py` or `python3`.
