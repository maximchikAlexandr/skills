#!/usr/bin/env python3
"""AI-skill candidates in Vidra's existing SQLite database."""
import argparse,json,os,sqlite3
from datetime import datetime,timezone
from pathlib import Path
DB=Path(os.environ.get("VIDRA_HOME",Path.home()/".vidra"))/"vidra.sqlite3"
def db():
 DB.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.executescript("CREATE TABLE IF NOT EXISTS skill_candidates(id INTEGER PRIMARY KEY,repository_key TEXT NOT NULL COLLATE NOCASE,skill_path TEXT NOT NULL,source_url TEXT NOT NULL,revision TEXT NOT NULL,stars INTEGER NOT NULL,license TEXT,category TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'discovered',discovered_at TEXT NOT NULL,UNIQUE(repository_key,skill_path));CREATE INDEX IF NOT EXISTS skill_candidates_category_idx ON skill_candidates(category,stars DESC);")
 return c
p=argparse.ArgumentParser();s=p.add_subparsers(dest="cmd",required=True)
q=s.add_parser("seen");q.add_argument("repository");q.add_argument("skill_path")
q=s.add_parser("add");q.add_argument("repository");q.add_argument("skill_path");q.add_argument("--source-url",required=True);q.add_argument("--revision",required=True);q.add_argument("--stars",type=int,required=True);q.add_argument("--license");q.add_argument("--category",required=True)
q=s.add_parser("list");q.add_argument("--category")
a=p.parse_args();c=db()
if a.cmd=="seen":
 r=c.execute("SELECT * FROM skill_candidates WHERE repository_key=? AND skill_path=?",(a.repository.lower(),a.skill_path)).fetchone();print(json.dumps(dict(r) if r else {"seen":False},ensure_ascii=False))
elif a.cmd=="add":
 if a.stars<200:raise SystemExit("candidate requires at least 200 stars")
 c.execute("INSERT INTO skill_candidates(repository_key,skill_path,source_url,revision,stars,license,category,discovered_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(repository_key,skill_path) DO UPDATE SET source_url=excluded.source_url,revision=excluded.revision,stars=excluded.stars,license=excluded.license,category=excluded.category",(a.repository.lower(),a.skill_path,a.source_url,a.revision,a.stars,a.license,a.category,datetime.now(timezone.utc).isoformat()));c.commit();print('{"result":"recorded"}')
else:
 sql="SELECT * FROM skill_candidates";args=()
 if a.category:sql+=" WHERE category=?";args=(a.category,)
 print(json.dumps([dict(r) for r in c.execute(sql+" ORDER BY stars DESC",args)],ensure_ascii=False,indent=2))

