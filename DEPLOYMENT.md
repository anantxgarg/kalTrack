# Deploying to Render

This FastAPI application is ready to deploy to Render. You have two deployment options:

## Option 1: Using Blueprint (render.yaml) - Recommended

1. **Connect your repository to Render:**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click "New" → "Blueprint"
   - Connect your GitHub/GitLab repository
   - Render will automatically detect the `render.yaml` file

2. **Set environment variables:**
   - In the Render dashboard, go to your service settings
   - Add the environment variable:
     - `GROQ_API_KEY`: Your actual Groq API key

3. **Deploy:**
   - Render will automatically build and deploy your application
   - Your app will be available at the provided Render URL

## Option 2: Manual Web Service

1. **Create a new Web Service:**
   - Go to Render Dashboard
   - Click "New" → "Web Service"
   - Connect your repository

2. **Configure the service:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Python Version:** 3.11.0

3. **Set environment variables:**
   - Add `GROQ_API_KEY` with your actual API key

## Important Notes

- **Environment Variables:** Never commit your actual API keys to the repository. Set them in Render's dashboard.
- **Static Files:** Your static files in the `/static` directory will be served correctly.
- **Database:** If you need persistent storage, consider adding a PostgreSQL database service in Render.
- **Custom Domain:** You can add a custom domain in the Render dashboard after deployment.

## Local Testing

Before deploying, test locally:
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Your app will be available at `http://localhost:8000`