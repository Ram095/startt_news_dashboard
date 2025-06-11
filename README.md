# Startt AI News Management Dashboard

A comprehensive news management and publishing platform built with Streamlit, featuring AI-powered content analysis, automated publishing, and an intuitive dashboard interface.

## 🚀 Features

- **News Aggregation**: Automated scraping from multiple news sources
- **AI-Powered Analysis**: Content analysis, sentiment analysis, and duplicate detection
- **Content Management**: Article approval workflow and bulk operations
- **Publishing Pipeline**: Automated publishing to multiple platforms
- **Analytics Dashboard**: Real-time metrics and performance monitoring
- **Dark/Light Mode**: Customizable UI with theme support
- **Responsive Design**: Optimized for various screen sizes

## 📁 Project Structure

```
news-dashboard/
├── app/                    # Main application directory
│   ├── config/            # Configuration files
│   ├── database/          # Database management
│   ├── models/            # Data models
│   ├── repository/        # Data access layer
│   ├── services/          # Business logic
│   ├── utils/             # Utility functions
│   ├── ui_components/     # Reusable UI components
│   ├── pages/            # Streamlit pages
│   └── main.py           # Main application entry point
├── data/                  # Data storage
├── scripts/              # Utility scripts
├── requirements.txt      # Python dependencies
├── config.yaml          # Application configuration
└── setup.sh             # Setup script
```

## 🛠️ Key Components

### Models (`app/models/`)
- `Article`: Core data model for news articles
- `ArticleStatus`: Article workflow states (PULLED, APPROVED, PUBLISHED, REJECTED)
- `PublishStatus`: Publishing states (SUCCESS, FAILED, RETRY, SKIPPED)
- `ScraperRun`: Scraping execution tracking
- `PublishResult`: Publishing operation results
- `ActivityLog`: System activity logging

### Services (`app/services/`)
- `ContentService`: Article processing and management
- `ContentAnalyzer`: AI-powered content analysis
- `ScraperManager`: News source scraping coordination

### Repository (`app/repository/`)
- `ArticleRepository`: Data access layer for articles
- Database operations and query management

### Utils (`app/utils/`)
- `APIPublisher`: Publishing platform integration
- `UILogger`: UI logging and notifications
- `ImportCSVData`: Data import utilities

## 🚀 Getting Started

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Jayluci4/news-dashboard
cd news-dashboard
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up the environment:
```bash
./setup.sh
```

5. Configure the application:
- Copy `config.yaml.example` to `config.yaml`
- Update configuration values as needed

### Running the Application

```bash
streamlit run app/main.py
```

## 📚 Key Libraries Used

- **Streamlit**: Web application framework
- **Pandas**: Data manipulation and analysis
- **SQLAlchemy**: Database ORM
- **Plotly**: Interactive data visualization
- **OpenAI**: AI-powered content analysis
- **Sentence-Transformers**: Text similarity and analysis
- **NLTK**: Natural language processing
- **BeautifulSoup4**: Web scraping
- **FastAPI**: API development
- **Celery**: Task queue management
- **Redis**: Caching and message broker

## 🔧 Development

### Code Style
- Follow PEP 8 guidelines
- Use type hints
- Document functions and classes

### Testing
```bash
pytest
```

### Linting
```bash
flake8
black .
mypy .
```

## 📝 License

[Your License Here]

## 👥 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📞 Support

For support, please [open an issue](https://github.com/Jayluci4/news-dashboard/issues) or contact [contact@startt.in]. 