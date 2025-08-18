# Developer Guide

## Quirks

### AWS CloudFormation

__01 CF template YAML line break fold `>-` doesn't work__
for details see issue [CF API log format #9](https://github.com/yayfalafels/mcfpipe/issues/9)

Use **continuous single lines** in CF templates. The expected YAML line break folding behavior using `>-` doesn't work as expected, reason unknown but suspected cause is related to dangling characters `\r` from discrepancy between Windows `\r\n` and Linux  `\n` line break

X with line breaks
should work, but doesn't

```yaml
        Format: >-
          { "requestId":"$context.requestId","ip":"$context.identity.sourceIp",
            "caller":"$context.identity.caller","user":"$context.identity.user",
            "requestTime":"$context.requestTime","httpMethod":"$context.httpMethod",
```

OK single line

```yaml
        Format: >-
          { "requestId":"$context.requestId","ip":"$context.identity.sourceIp", "caller":"$context.identity.caller","user":"$context.identity.user", "requestTime":"$context.requestTime","httpMethod":"$context.httpMethod",
```
