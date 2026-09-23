# Make the project your own

Run the demo, then trace one accepted record, one duplicate, and one rejection through `pipeline.py`.

## Small contribution

Add an optional `--term` filter to report generation. Test that other terms cannot affect the selected term's results or suppression decisions. Use a bound SQL parameter.

## More substantial contribution

Add an enrollment CSV and compute response rates. Decide how to handle unknown courses, zero enrollment, and counts above enrollment. Label response rate separately from favorable percentage. Document the denominator and keep suppression rules consistent in both output formats.

## Advanced contribution

Add a revision workflow for legitimate corrected answers. Preserve the original answer, record who/what authorized the correction, and make reruns deterministic. Do not simply overwrite conflicting response IDs.

## Be ready to explain

1. Why are both file hashes and response IDs needed?
2. What failures should reject one row versus the whole file?
3. Why can removing names still fail to protect someone's identity?
4. How do transactions make reruns safe after a crash?
5. How would you adapt this pipeline to SQL Server or a scheduled job?

Use your own extension and tests to build a concrete story. This is new personal Python work; the adjacent reporting experience in an employment history does not establish past Python use.
