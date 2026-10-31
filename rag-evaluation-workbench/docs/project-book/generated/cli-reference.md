# CLI reference

Captured from the argparse definitions in `src/rag_workbench/cli.py`.

```text
usage: ragwb [-h] [--version]
             {run,list,tag,note,regress,user,judge-noise,restore,tune-abstention,show,compare,export,validate,delete,metrics,import,score,labels-template,calibrate,slices,rerun,backup,prune,doctor}
             ...

RAG Evaluation Workbench: evaluate a retrieval-augmented QA pipeline over a
dataset.

positional arguments:
  {run,list,tag,note,regress,user,judge-noise,restore,tune-abstention,show,compare,export,validate,delete,metrics,import,score,labels-template,calibrate,slices,rerun,backup,prune,doctor}
    run                 run an evaluation
    list                list stored runs (optionally filtered)
    tag                 add or remove tags on a run
    note                set or clear a run's note
    regress             fail when a candidate run is significantly worse than
                        a baseline run
    user                manage named accounts for the web app (add, remove,
                        set-role, list)
    judge-noise         re-score a run's answers several times to measure
                        judge jitter (makes API calls)
    restore             replace the run store with a backup (writes a safety
                        copy first)
    tune-abstention     pick the offline abstention threshold on a development
                        half and report it on a held-out half
    show                show one run
    compare             paired comparison of run B against run A
    export              export a run
    validate            validate a dataset file (exit code 1 if it is invalid)
    delete              delete a stored run
    metrics             describe available metrics
    import              import run bundles written by 'export --format json'
    score               score a single answer with selected metrics (nothing
                        is stored)
    labels-template     write a CSV for human labelling of a run's cases
    calibrate           compare a metric's pass/fail with labels (agreement,
                        kappa)
    slices              summarise a run per value of a dataset metadata field
    rerun               repeat a stored run from its recorded configuration
    backup              write a verified copy of the run store
    prune               delete old runs by retention policy (dry run unless
                        --yes)
    doctor              check the installation, configuration and run store
                        (no network calls)

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## `ragwb run`

```text
usage: ragwb run [-h] [--name NAME] [--dataset DATASET] [--document DOCUMENT]
                 [--provider {offline,openai}] [--pipeline {rag,agent}]
                 [--retriever {bm25,embedding,hybrid,local,hybrid-local}]
                 [-k K] [--metrics METRICS] [--threshold METRIC=VALUE]
                 [--model MODEL] [--judge-model JUDGE_MODEL]
                 [--workers WORKERS] [--limit LIMIT]
                 [--answer-sentences ANSWER_SENTENCES]
                 [--inject-failures INJECT_FAILURES]
                 [--min-evidence MIN_EVIDENCE] [--skip-headings] [--seed SEED]
                 [--notes NOTES] [--quiet]

options:
  -h, --help            show this help message and exit
  --name NAME           human-readable run name
  --dataset DATASET     dataset .jsonl/.csv (default:
                        examples/datasets/honeybees.jsonl)
  --document DOCUMENT   source .pdf/.txt/.md (default:
                        examples/documents/honeybees.pdf)
  --provider {offline,openai}
  --pipeline {rag,agent}
  --retriever {bm25,embedding,hybrid,local,hybrid-local}
                        embedding/hybrid use an embeddings API (needs
                        OPENAI_API_KEY); local/hybrid-local use a local model
                        (needs the optional fastembed package, no key); hybrid
                        = BM25 + dense fused by reciprocal rank
  -k K                  chunks retrieved per query
  --metrics METRICS     comma-separated; available: exact_match,token_f1,rouge
                        _l,context_recall,groundedness,semantic_similarity,sem
                        antic_context_recall,answer_relevancy,faithfulness,con
                        text_relevancy,correctness
  --threshold METRIC=VALUE
                        override a pass threshold
  --model MODEL         generator model (openai provider)
  --judge-model JUDGE_MODEL
                        DeepEval judge model
  --workers WORKERS     parallel cases (default: 1 offline; RAGWB_MAX_WORKERS
                        with a provider)
  --limit LIMIT         evaluate only the first N cases (default: all)
  --answer-sentences ANSWER_SENTENCES
                        offline generator: sentences per answer
  --inject-failures INJECT_FAILURES
                        offline: fraction of cases that fail
  --min-evidence MIN_EVIDENCE
                        offline: abstain unless the answer covers this share
                        (0-1) of the question's terms
  --skip-headings       drop heading-like blocks from the chunks
  --seed SEED
  --notes NOTES
  --quiet
```

## `ragwb list`

```text
usage: ragwb list [-h] [--search WORD [WORD ...]] [--tag TAG]
                  [--status STATUS]

options:
  -h, --help            show this help message and exit
  --search WORD [WORD ...]
                        words that must all appear in the run's id, name,
                        notes, tags, status, provider, retriever or file names
  --tag TAG             only runs with this tag
  --status STATUS       only runs with this status
```

## `ragwb tag`

```text
usage: ragwb tag [-h] [--add ADD] [--remove REMOVE] run_id

positional arguments:
  run_id

options:
  -h, --help       show this help message and exit
  --add ADD        comma-separated tags to add
  --remove REMOVE  comma-separated tags to remove
```

## `ragwb note`

```text
usage: ragwb note [-h] [--clear] run_id [text]

positional arguments:
  run_id
  text

options:
  -h, --help  show this help message and exit
  --clear
```

## `ragwb regress`

```text
usage: ragwb regress [-h] [--max-drop MAX_DROP] [--min-pairs MIN_PAIRS]
                     [--max-error-increase MAX_ERROR_INCREASE]
                     [--metrics METRICS]
                     baseline candidate

positional arguments:
  baseline
  candidate

options:
  -h, --help            show this help message and exit
  --max-drop MAX_DROP   largest tolerated drop in a metric mean (0.02)
  --min-pairs MIN_PAIRS
                        paired questions needed to judge a metric (10)
  --max-error-increase MAX_ERROR_INCREASE
                        largest tolerated rise in the share of failed cases
                        (0.05)
  --metrics METRICS     comma-separated metrics to gate (default: all shared)
```

## `ragwb user`

```text
usage: ragwb user [-h] [--role {viewer,editor,admin}] [--replace]
                  [--password-stdin] [--force]
                  {add,remove,set-role,set-password,list} [name]

positional arguments:
  {add,remove,set-role,set-password,list}
  name

options:
  -h, --help            show this help message and exit
  --role {viewer,editor,admin}
                        with add or set-role: viewer (read-only), editor
                        (default: run, tag), admin (also delete runs)
  --replace             with add: change an existing user's password
  --password-stdin      read the password from standard input
  --force               remove/demote even the last admin
```

## `ragwb judge-noise`

```text
usage: ragwb judge-noise [-h] [--repeats REPEATS] [--metrics METRICS]
                         [--limit LIMIT] [--yes]
                         run_id

positional arguments:
  run_id

options:
  -h, --help         show this help message and exit
  --repeats REPEATS  scorings per case and metric (2 or more, default 3)
  --metrics METRICS  comma-separated judge metrics (default: the run's judge
                     metrics)
  --limit LIMIT      only the first N cases
  --yes              confirm a large number of judge calls
```

## `ragwb restore`

```text
usage: ragwb restore [-h] [--yes] [--force] backup

positional arguments:
  backup      a file made by `ragwb backup`

options:
  -h, --help  show this help message and exit
  --yes       confirm the replacement
  --force     replace even if a run looks active
```

## `ragwb tune-abstention`

```text
usage: ragwb tune-abstention [-h] [--dataset DATASET [DATASET ...]]
                             [--document DOCUMENT [DOCUMENT ...]]

options:
  -h, --help            show this help message and exit
  --dataset DATASET [DATASET ...]
                        datasets (default: the bundled examples with
                        unanswerable rows)
  --document DOCUMENT [DOCUMENT ...]
                        documents, in the same order as --dataset
```

## `ragwb show`

```text
usage: ragwb show [-h] run_id

positional arguments:
  run_id

options:
  -h, --help  show this help message and exit
```

## `ragwb compare`

```text
usage: ragwb compare [-h] run_a run_b

positional arguments:
  run_a
  run_b

options:
  -h, --help  show this help message and exit
```

## `ragwb export`

```text
usage: ragwb export [-h] [--format {csv,json,md}] [--out-dir OUT_DIR] run_id

positional arguments:
  run_id

options:
  -h, --help            show this help message and exit
  --format {csv,json,md}
  --out-dir OUT_DIR
```

## `ragwb validate`

```text
usage: ragwb validate [-h] dataset

positional arguments:
  dataset

options:
  -h, --help  show this help message and exit
```

## `ragwb delete`

```text
usage: ragwb delete [-h] [--yes] run_id

positional arguments:
  run_id

options:
  -h, --help  show this help message and exit
  --yes       confirm deletion
```

## `ragwb metrics`

```text
usage: ragwb metrics [-h]

options:
  -h, --help  show this help message and exit
```

## `ragwb import`

```text
usage: ragwb import [-h] bundles [bundles ...]

positional arguments:
  bundles     bundle .json files

options:
  -h, --help  show this help message and exit
```

## `ragwb score`

```text
usage: ragwb score [-h] --question QUESTION --answer ANSWER
                   [--expected EXPECTED] [--context CONTEXT]
                   [--metrics METRICS] [--judge-model JUDGE_MODEL]

options:
  -h, --help            show this help message and exit
  --question QUESTION
  --answer ANSWER
  --expected EXPECTED   reference answer
  --context CONTEXT     a context passage (repeatable)
  --metrics METRICS
  --judge-model JUDGE_MODEL
```

## `ragwb labels-template`

```text
usage: ragwb labels-template [-h] --out OUT [--force] run_id

positional arguments:
  run_id

options:
  -h, --help  show this help message and exit
  --out OUT
  --force
```

## `ragwb calibrate`

```text
usage: ragwb calibrate [-h] --labels LABELS --metric METRIC [--sweep]
                       [--rescore]
                       run_id

positional arguments:
  run_id

options:
  -h, --help       show this help message and exit
  --labels LABELS  .csv (case_id,human_pass) or .jsonl
  --metric METRIC
  --sweep          also show agreement at each pass threshold (0.10-0.95)
  --rescore        compute an offline or local-model metric the run does not
                   have from its stored answers (no API calls)
```

## `ragwb slices`

```text
usage: ragwb slices [-h] --by BY run_id

positional arguments:
  run_id

options:
  -h, --help  show this help message and exit
  --by BY     metadata field, e.g. type
```

## `ragwb rerun`

```text
usage: ragwb rerun [-h] [--name NAME] [--quiet] run_id

positional arguments:
  run_id

options:
  -h, --help   show this help message and exit
  --name NAME  name for the new run (default: <old name>-rerun)
  --quiet
```

## `ragwb backup`

```text
usage: ragwb backup [-h] [--out-dir OUT_DIR]

options:
  -h, --help         show this help message and exit
  --out-dir OUT_DIR  default: <data dir>/backups
```

## `ragwb prune`

```text
usage: ragwb prune [-h] [--keep-last KEEP_LAST]
                   [--older-than-days OLDER_THAN_DAYS] [--yes]

options:
  -h, --help            show this help message and exit
  --keep-last KEEP_LAST
                        always keep the newest N runs
  --older-than-days OLDER_THAN_DAYS
                        select runs created more than D days ago
  --yes                 actually delete
```

## `ragwb doctor`

```text
usage: ragwb doctor [-h]

options:
  -h, --help  show this help message and exit
```
