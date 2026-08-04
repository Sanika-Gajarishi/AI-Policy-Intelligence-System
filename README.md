# 🌍 ClimateHub AI Policy Dashboard

> An intelligent AI-powered platform for analyzing, searching, and exploring climate policy documents — built for researchers, policymakers, and organizations working on climate action.

---

## 📌 Overview

The **ClimateHub AI Policy Dashboard** is a full-stack web application that enables users to upload, index, and query climate policy documents using advanced AI. It leverages vector search and large language models to provide accurate, context-aware answers from a curated document database.

---

## ✨ Features

- 🔍 **AI-Powered Search** — Ask questions in natural language and get answers from policy documents
- 📄 **Document Upload & Indexing** — Upload PDFs and automatically index them for semantic search
- 🧠 **Claude AI Integration** — Powered by Anthropic's Claude for intelligent responses
- ☁️ **Google Drive Integration** — Bulk upload and sync documents from Google Drive
- 📊 **Export Results** — Export query results and reports
- 🗂️ **Vector Store** — Fast semantic search using ChromaDB
- 🌐 **Modern React Frontend** — Clean, responsive UI for seamless user experience
- 🔄 **Real-time Query Processing** — Instant responses with session management

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| Python + Flask | REST API server |
| Anthropic Claude | AI language model |
| ChromaDB | Vector store for semantic search |
| Tesseract OCR | PDF text extraction |
| Google Drive API | Document sync |

### Frontend
| Technology | Purpose |
|---|---|
| React.js | UI framework |
| Node.js | Runtime environment |
| Nginx | Web server & reverse proxy |

---

## 📁 Project Structure

```
AI-Policy-Dashboard/
├── backend/
│   ├── app.py                    # Main Flask application
│   ├── routes/
│   │   ├── query.py              # Query handling routes
│   │   └── export.py             # Export functionality
│   ├── services/
│   │   ├── claude.py             # Claude AI integration
│   │   └── google_drive_service.py
│   ├── data/                     # Document storage (gitignored)
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── src/                      # React source files
│   └── package.json
├── .gitignore
├── README.md
└── TROUBLESHOOTING.md
```

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- Tesseract OCR
- Google Cloud credentials
- Anthropic API key

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Add your API keys to .env
```

### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

### Environment Variables

Create a `.env` file in the `backend/` folder:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_DRIVE_CREDENTIALS=path_to_credentials.json
```

---

## 🚀 Running the Application

### Start Backend
```bash
cd backend
python app.py
```

### Start Frontend
```bash
cd frontend
npm start
```

The app will be available at `http://localhost:3000`

---

## ☁️ Deployment

This project is deployed on **Google Cloud Run** with continuous deployment from this GitHub repository.

- **Backend:** Python Flask service on Cloud Run
- **Frontend:** React app served via Nginx on Cloud Run
- **CI/CD:** Automatic builds triggered on push to `main` branch

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📧 Contact

**Organization:** [chia-stack](https://github.com/chia-stack)  
**Email:** sanika@climatehub.in  
**Project:** [AI-Policy-Dashboard](https://github.com/chia-stack/AI-Policy-Dashboard)

---

## 📄 License

This project is private and proprietary to **ClimateHub / chia-stack**.

---

*Built with ❤️ for Climate Action*