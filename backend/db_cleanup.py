import sqlite3, os
p=os.path.join('backend','vri.db')
conn=sqlite3.connect(p)
c=conn.cursor()
c.execute("DELETE FROM analysis_results WHERE query_text=?", ('banana is a fruit',))
conn.commit()
print('deleted', c.rowcount)
conn.close()
