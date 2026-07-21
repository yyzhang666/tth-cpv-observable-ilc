# HTCondor batch processing on the NAF

Any task touching more than a few chunks (kinfit over 80 chunks, full feature
exports, trainings on the 1M-event samples) must run on HTCondor, not on the
login/interactive node.

## The pattern

Every condor workflow here has three parts:

```
condor/example/job_wrapper.sh      what ONE job does (sources env, runs one chunk)
condor/example/make_arguments.py   writes arguments.txt (one line per job)
condor/example/submit_kinfit.sub   submit file: queue ... from arguments.txt
```

Submit and monitor:

```bash
cd condor/example
python3 make_arguments.py --config ../../configs/analysis_ow_lr.yaml   # -> arguments.txt
mkdir -p log out err
condor_submit submit_kinfit.sub
condor_q                      # watch
condor_history -limit 5       # after completion
```

The default component is the CPV-interference reco sample. To produce the SM
denominator with the identical kinfit selection, generate a separate argument
file and submit it separately:

```bash
python3 make_arguments.py \
  --config ../../configs/analysis_ow_lr.yaml \
  --component sm
condor_submit submit_kinfit.sub
```

## Non-negotiable rules (learned the hard way)

1. **One job = one chunk = one job-local work directory.** Marlin writes
   hidden fixed-name files (e.g. `Output.root`) into its CWD; two jobs
   sharing a CWD corrupt each other. The repo wrappers already do this —
   keep the pattern in anything you add.
2. **Success = validated content.** Check the job log, stderr, exit code,
   AND the output content (event counts, tree entries, and the
   `logchi2_plus_flavor` final-selection branches). The kinfit wrapper runs
   `scripts/validate_kinfit_root.py`; keep that validation step in any derived
   workflow. File existence alone is a common trap.
3. **Production artifacts stay immutable.** The wrappers refuse overwrites;
   for a re-run, use a fresh output directory.
4. **Held after ~default runtime?** Raise `+RequestRuntime` in the submit
   file and resubmit (killed jobs need a resubmit, `condor_release` applies
   to held-but-alive jobs only).
5. **Smoke test first.** Submit ONE job (`queue 1` or a one-line
   arguments.txt) and validate it end-to-end before submitting 80.
6. Logs (`log/ out/ err/`) live under `outputs/` or the condor example dir —
   both gitignored.
7. Known Marlin quirk: `TTHSemiLepKinFit` finalization may crash with exit
   134/139 AFTER writing a valid ROOT file. The wrapper accepts these exits
   only when the ROOT file is non-empty and the content validator passes.

## Resource guidance

| task | request_memory | typical runtime per chunk |
|---|---|---|
| kinfit one chunk (12.5k events) | 4 GB | O(hours) |
| gen feature export one chunk | 2 GB | O(10 min) |
| CatBoost training (exported CSVs) | 8 GB | O(30 min) |

Adjust after measuring the smoke job (`condor_history -long <id> | grep -i
memory`).

## Adapting the example to another task

Copy the three files, change only:
- the command inside `job_wrapper.sh` (keep the env sourcing + work-dir logic);
- the per-job argument list in `make_arguments.py`;
- resource requests in the `.sub` file.

Keep the wrapper executable (`chmod +x`).
