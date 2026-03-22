# Trinetra — Insurance Automation Platform

> An intelligent, end-to-end insurance automation platform powered by AI/ML — streamlining claims, detecting fraud, managing policies, and assessing risk with precision.

## 🎬 Demo

[![Watch Demo](https://img.shields.io/badge/Watch-Demo-blue?logo=googledrive&style=for-the-badge)](https://drive.google.com/file/d/1kxVvMh3pEdsU7B3ISRmeHn2RcwrOPcNd/view?usp=drive_link)

---

## 🚀 Features

- **⚡ Claims Automation** — Automates end-to-end insurance claim processing, reducing manual effort and turnaround time
- **🔍 Fraud Detection** — AI-powered anomaly detection to identify and flag suspicious claims in real time
- **📋 Policy Management** — Centralized dashboard to create, manage, and track insurance policies efficiently
- **📊 Risk Assessment** — ML models that evaluate and score risk profiles for smarter underwriting decisions

---

## 🏗 Architecture Overview
```
├── Frontend (React)
│   ├── Policy Management Dashboard
│   ├── Claims Tracking UI
│   ├── Risk Assessment Reports
│   └── Fraud Alert Interface
│
├── Backend (Python)
│   ├── REST APIs
│   ├── Business Logic Layer
│   └── Database Models
│
└── AI/ML Engine (Python)
    ├── Fraud Detection Model
    ├── Risk Scoring Model
    └── Claims Classification Model
```

---

## 🛠 Tech Stack

**Frontend**

![React](https://img.shields.io/badge/React-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
![JavaScript](https://img.shields.io/badge/JavaScript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)

**Backend & AI/ML**

![Python](https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![scikit-learn](https://img.shields.io/badge/scikit--learn-%23F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white)
![TensorFlow](https://img.shields.io/badge/TensorFlow-%23FF6F00.svg?style=for-the-badge&logo=TensorFlow&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)

**Database**

![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)

---

## ⚙️ Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- MySQL

### Backend Setup
```bash
# Clone the repository
git clone https://github.com/march-M-R/trinetra.git
cd trinetra

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the backend server
python app.py
```

### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm start
```

### Environment Variables

Create a `.env` file in the root directory:
```env
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=trinetra_db
SECRET_KEY=your_secret_key
```

---

## 👩‍💻 Author

**Mahathi Rachavelpula**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-%230077B5.svg?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/mahathi9/)
[![GitHub](https://img.shields.io/badge/GitHub-%23121011.svg?style=for-the-badge&logo=github&logoColor=white)](https://github.com/march-M-R)

---

> ⭐ If you found this project useful, consider giving it a star!
