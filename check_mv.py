from django.db import connection

cur = connection.cursor()
cur.execute("SELECT schemaname, matviewname FROM pg_matviews WHERE schemaname = 'gold'")
print("MVs gold:", cur.fetchall())

cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'bronze' ORDER BY tablename")
print("Tablas bronze:", cur.fetchall())

cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'silver' ORDER BY tablename")
print("Tablas silver:", cur.fetchall())

cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'gold' ORDER BY tablename")
print("Tablas gold:", cur.fetchall())