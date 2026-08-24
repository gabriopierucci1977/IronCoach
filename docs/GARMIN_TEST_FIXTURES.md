# Garmin FIT test fixtures

The two FIT samples used by the parser regression tests are intentionally not
stored in the public repository because Garmin exports can contain athlete and
device data.

The affected tests are:

- `tests/test_garmin_importer.py`
- `tests/test_garmin_multisport.py`

A clean clone therefore **skips** these tests when the private fixtures are not
available. All other tests continue to run normally.

## Default local location

```text
data/garmin_raw/4872731416_ACTIVITY.fit
data/garmin_raw/14891176843_ACTIVITY.fit
```

`data/` remains gitignored.

## Alternative fixture directory

Set:

```text
IRONCOACH_GARMIN_FIXTURE_DIR=/path/to/private/garmin/fixtures
```

The tests will look for both files in that directory.

## CI behavior

Public CI runs the complete test command. The five tests that need private FIT
files are reported as skipped rather than failed. A private CI runner can set
`IRONCOACH_GARMIN_FIXTURE_DIR` to execute them as well.
