from datadog_lambda.pb.span_pb2 import Span
from datadog_lambda.pb.trace_pb2 import APITrace
from datadog_lambda.pb.trace_payload_pb2 import TracePayload
from datadog_lambda import __version__
from datadog_lambda.config import get_config
import sys

if sys.version_info >= (3, 0, 0):
    import urllib.request as urllib
else:
    import urllib2 as urllib


class TraceConnection:
    def __init__(self, rootURL, apiKey):
        self._traceURL = "https://trace.agent.{}/api/v0.2/traces".format(rootURL)
        self._apiKey = apiKey

    def send_spans(self, spans):
        trace_payload = convert_trace_to_protobuf_payload(spans)
        data = trace_payload.SerializeToString()
        user_agent = "aws_lambda/{}/1 (http://localhost)".format(__version__)
        cont_len = len(data)
        headers = {
            "Content-Type": "application/x-protobuf",
            "Content-Encoding": "identity",
            "DD-Api-Key": self._apiKey,
            "User-Agent": user_agent,
            "Content-Length": cont_len,
        }
        try:
            request = urllib.Request(self._traceURL, data, headers)
            urllib.urlopen(request)
        except urllib.HTTPError as e:
            print("request to {} failed with error {}".format(self._traceURL, e))


def convert_trace_to_protobuf_payload(trace):
    span_groups = {}

    for span in trace:
        trace_id = int(span["trace_id"])
        span_group = []
        if trace_id in span_groups:
            span_group = span_groups[trace_id]
        else:
            span_groups[trace_id] = span_group

        args = {
            "service": span["service"],
            "name": span["name"],
            "resource": span["resource"],
            "traceID": trace_id,
            "spanID": int(span["span_id"]),
            "start": span["start"],
            "duration": span["duration"],
            "error": span["error"],
            "meta": span["meta"],
            "metrics": span["metrics"],
            "type": "",
        }

        if "parent_id" in span:
            args["parentID"] = int(span["parent_id"])

        span_group.append(Span(**args))

    traces = []
    for trace_id, span_group in span_groups.items():
        first_span = span_group[0]
        traces.append(
            APITrace(
                traceID=trace_id,
                spans=span_group,
                startTime=first_span.start,
                endTime=first_span.start + first_span.duration,
            )
        )
        trace_payload = TracePayload(hostName="none", env="none", traces=traces)
    return trace_payload


def forward_traces(traces):
    api_key, host = get_config()
    conn = TraceConnection(host, api_key)
    conn.send_spans(traces)
