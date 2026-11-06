"""Run one of three approved metric questions against an existing local build."""
import argparse
import sqlite3
from pathlib import Path
from pipeline import ask

parser=argparse.ArgumentParser()
parser.add_argument("question")
parser.add_argument("--database",type=Path,default=Path("outputs/revenue.sqlite"))
args=parser.parse_args()
with sqlite3.connect(f"file:{args.database.resolve()}?mode=ro",uri=True) as con:
    sql,frame=ask(con,args.question)
    print(sql)
    print(frame.to_csv(index=False))
