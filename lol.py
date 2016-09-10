"""
We use a content addressable key-value store to name calls by (function, arguments),
where function is named by a hash of its contents.  We use the python `dill' library
to name the function by its contents, including its code and anything it may capture,
recursively.

This may be useful to memoize unit tests across code changes.

This is a proof of concept; don't actually use it to try to speed up your unit tests.
dill is capturing more than it strictly needs to, which means hashes mismatch and there
are false negatives.  Also there's no garbage collection of memoized data.
"""

# INSTALLATION: run `pip install dill`

import sqlite3
import hashlib
import dill

def hash(obj):
    return hashlib.sha224(dill.dumps(obj)).hexdigest()

conn = sqlite3.connect('memoized.db')

# TEXT type for this connection is bytes, not unicode
conn.text_factory = str

# Turn on autocommit for every transaction
conn.isolation_level = None

# idempotently set up the schema
conn.execute('''create table if not exists pairs (input_hash blob, value blob)''')

cur = conn.cursor()  # should be thread local, I think

def memoize(fn, call_hook=(lambda found_cached, call_hash: None)):
    # precompute the fn's hash
    fn_hash = hash(fn)

    def wrapper(*args, **kwargs):
        call_hash = hash((fn_hash, args, kwargs))

        cur.execute("select value from pairs where input_hash = ?", (call_hash,))
        saved = cur.fetchone()

        did_find_cached = (saved != None)

        if did_find_cached:
            result = dill.loads(saved[0])

        else:
            result = fn(*args, **kwargs)
            cur.execute("insert into pairs VALUES (?, ?)", (call_hash, dill.dumps(result)))

        call_hook(did_find_cached, call_hash)

        return result
    return wrapper

# demo utility

def memoize_and_log_misses(fn):
    def do_print(found_cached, call_hash):
        if not found_cached:
            print "executed new", call_hash

    return memoize(fn, do_print)

# examples

@memoize_and_log_misses
def simple():
    print 'hello world!'

@memoize_and_log_misses
def fib(a):
    if a < 2:
        return 1
    else:
        return a * fib(a - 1)

for i in range(10):
    simple()

print sum([fib(i) for i in range(20)])
