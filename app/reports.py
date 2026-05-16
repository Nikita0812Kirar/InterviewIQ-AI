import html
import json


def build_report(interview: dict, messages: list[dict]) -> str:
    scores = [json.loads(m["score_json"]) for m in messages if m.get("score_json")]
    avg = round(sum(item["overall_score"] for item in scores) / len(scores), 1) if scores else 0
    improvements = []
    for item in scores:
        improvements.extend(item.get("improvements", []))
    unique_improvements = list(dict.fromkeys(improvements))[:6]
    transcript = "".join(
        f"<p><strong>{html.escape(m['sender'])} - {html.escape(m['agent'])}:</strong> {html.escape(m['content'])}</p>"
        for m in messages
    )
    tips = "".join(f"<li>{html.escape(tip)}</li>" for tip in unique_improvements)
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Interview Report</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 32px; color: #18202f; }}
        h1, h2 {{ color: #0f766e; }}
        .score {{ font-size: 40px; font-weight: 800; }}
        section {{ border-top: 1px solid #dbe4ee; padding-top: 16px; margin-top: 16px; }}
        .toolbar {{
          display: flex;
          gap: 10px;
          justify-content: flex-end;
          margin-bottom: 24px;
          flex-wrap: wrap;
        }}
        button, a.button {{
          border: 0;
          border-radius: 8px;
          background: #0f766e;
          color: white;
          cursor: pointer;
          display: inline-block;
          font: inherit;
          font-weight: 700;
          padding: 10px 14px;
          text-decoration: none;
        }}
        button.secondary {{ background: #334155; }}
        @media print {{ .toolbar {{ display: none; }} body {{ margin: 18px; }} }}
      </style>
    </head>
    <body>
      <div class="toolbar">
        <button class="secondary" onclick="goBack()">Back</button>
        <a class="button" id="downloadLink" href="#">Download Report</a>
        <button onclick="window.print()">Print / Save PDF</button>
      </div>
      <h1>AI Interview Report</h1>
      <p>{html.escape(interview['role'])} - {html.escape(interview['level'])} - {html.escape(interview['company'])}</p>
      <div class="score">{avg}/10</div>
      <section><h2>Improvement Roadmap</h2><ul>{tips}</ul></section>
      <section><h2>Transcript</h2>{transcript}</section>
      <script>
        function goBack() {{
          if (window.history.length > 1) {{
            window.history.back();
          }} else {{
            window.location.href = "/";
          }}
        }}
        const url = new URL(window.location.href);
        url.searchParams.set("download", "1");
        document.getElementById("downloadLink").href = url.toString();
      </script>
    </body>
    </html>
    """
