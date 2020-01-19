import praw
from praw.models import Comment
import json
import time
import threading
import hashlib


class AuthorThread(threading.Thread):
    def __init__(self, reddit=None, cids=None, dateline=None):
        super().__init__()
        self.reddit = reddit
        self.cids = cids
        self.authors = []
        self.dateline = dateline
        self.dq_age = set()

    def run(self):
        for cid in self.cids:
            author = Comment(self.reddit, id=cid).author
            try:
                if author is None:
                    self.authors.append("Null")
                    continue

                if author.created_utc > self.dateline:
                    self.dq_age.add(author.name)

                self.authors.append(author.name)
            except:  # thread CANNOT crash
                self.authors.append('NULL*')


def mt_author(t_no=10, reddit=None, cids=None, dateline=None):
    total_len = len(cids)
    chunk_len = total_len // t_no + 1
    cid_chunks = [cids[x:x + chunk_len] for x in range(0, len(cids), chunk_len)]
    threads = []

    for i in range(t_no):
        if i == len(cid_chunks):
            break
        threads.append(AuthorThread(reddit=reddit, cids=cid_chunks[i], dateline=dateline))

    for thread in threads:
        thread.start()

    pct_done = 0.0
    done = 1
    hang = 0
    while pct_done < 99.51:
        old_done = done
        done = 0
        for thread in threads:
            done += len(thread.authors)
        pct_done = done / total_len * 100
        rate = (done - old_done) / 3
        etd = (1 / 60) * (total_len - done) / rate if rate != 0 else 999
        print("Progress: {}/{} ({:.2f}% - {:.2f}/s) ETD: {:.2f} minutes".format(done, total_len, pct_done, rate, etd))

        if rate == 0 and (hang := hang + 1) > 3:
            break
        elif rate != 0:
            hang = 0

        time.sleep(3)

    for thread in threads:
        thread.join()

    a_list = []
    dq_age = set()
    for thread in threads:
        a_list += thread.authors
        dq_age.update(thread.dq_age)

    return a_list, dq_age


def init_reddit():
    with open('auth.json', 'r') as f:
        auth = json.load(f)

    return praw.Reddit(
        client_id=auth['client_id'],
        client_secret=auth['client_secret'],
        username=auth['username'],
        password=auth['password'],
        user_agent=auth['user_agent'])


def hash_sha256(file):
    buf_size = 65536  # lets read stuff in 64kb chunks!
    sha256 = hashlib.sha256()
    with open(file, 'rb') as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


def main():
    with open('meta.json', 'r') as f:
        meta = json.load(f)

    file_name = meta['CID_Filename']
    dateline = meta['Dateline']
    threads = meta['Concurrent_Threads']

    with open(file_name, 'r') as f:
        comment_ids = [line.strip() for line in f]

    b = time.time()
    authors, dq_age = mt_author(t_no=threads, reddit=init_reddit(), cids=comment_ids, dateline=dateline)
    a = time.time()

    print("Took {:.2f}s to retrieve {} comment authors".format(a - b, len(comment_ids)))

    with open(file_name.rstrip('.txt') + '_Authors.txt', 'w') as f:
        f.write('\n'.join(authors))

    with open(file_name.rstrip('.txt') + '_DQ-Age.txt', 'w') as f:
        f.write('\n'.join(sorted(dq_age, key=str.casefold)))

    meta['AUID_SHA256'] = hash_sha256(file_name.rstrip('.txt') + '_Authors.txt')
    print(f"SHA-256 Hash: {meta['AUID_SHA256']}")

    with open('meta.json', 'w') as outfile:
        json.dump(meta, outfile, indent=4)

    x = input("Done!")


if __name__ == "__main__":
    main()
