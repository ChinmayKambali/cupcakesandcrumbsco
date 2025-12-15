# Cupcakes & Crumbs Co – Backend

## Run locally
cd backend
uvicorn main:app --reload


## Required environment variables (.env)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cupcakes_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password

ADMIN_KEY=your_admin_secret

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=yourgmail@gmail.com
EMAIL_PASS=your_gmail_app_password
EMAIL_FROM=yourgmail@gmail.com
EMAIL_TO=yourgmail@gmail.com