run-fetch:
	MEDIASTACK_API_KEY=$$(grep MEDIASTACK_API_KEY .env | cut -d '=' -f2) \
	DATABASE_URL=postgresql://postgres:postgres@localhost:5433/newsdb \
	PYTHONPATH=. python jobs/fetch_from_mediastack.py

clean-db:
	MEDIASTACK_API_KEY=$$(grep MEDIASTACK_API_KEY .env | cut -d '=' -f2) \
	DATABASE_URL=postgresql://postgres:postgres@localhost:5433/newsdb \
	PYTHONPATH=. python jobs/clean_articles.py

reset-db:
	DATABASE_URL=postgresql://postgres:postgres@localhost:5433/newsdb \
	PYTHONPATH=. python jobs/reset_db.py
