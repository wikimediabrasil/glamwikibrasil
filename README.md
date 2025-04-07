# GLAM-Wiki Brasil

This is a tool for report and tracking of Wikimedia Brasil GLAM-Wiki partnerships metrics

## 🚀 Features

- Export PDF monthly reports
- Track viewership metrics in charts

## 🛠 Tech Stack

- Languages: Python, JavaScript
- Framework: Django

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/wikimediabrasil/glamwikibrasil.git
cd glamwikibrasil

# Create and activate a virtual environment
python -m venv venv
source venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

You also need to set the configuration file:
```bash
cd glamwikibrasil

# Copy settings_local_example.py to settings_local.py
cp glamwikibrasil/settings_local_example.py glamwikibrasil/settings_local.py

# Set your configuration variables
SECRET_KEY = "YOUR_SECRET_KEY"
ALLOWED_HOSTS = ["YOUR ALLOWED HOSTS"]
LANGUAGES = ["LANGUAGES YOU WANT TO OPERATE"]
DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': BASE_DIR / 'database.sqlite3',
  }
}
```

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
