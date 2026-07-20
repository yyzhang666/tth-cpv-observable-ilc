# outputs/

All produced files live here and are gitignored (except this README).

Layout convention (created by the scripts):

```
outputs/<analysis_name>/
    features/       exported event tables + .meta.json
    angular/<obs>/  bin CSVs, plots, .fisher.json
    model/          trained model + model_metadata.json
    ml_observable/  score tables and templates
```

Every result directory must be reproducible from its `.meta.json` +
the configs it references. If it is not, it is not a result.
