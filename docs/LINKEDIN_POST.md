# LinkedIn Post — FinSage

---

For our Data Engineering capstone at Northeastern (DAMG 7374), we built FinSage — a system that generates 15-20 page equity research PDFs for any U.S. public company. Pick a ticker, get a report with 8 AI-refined charts, SEC filing analysis, and an investment thesis. Under 7 minutes. About $2 in compute.

The piece I keep coming back to is the Chart Agent. It writes matplotlib code, renders the chart, and then a Vision Language Model looks at the image and critiques it. "Axis labels overlap, rotate 45 degrees." The chart gets regenerated. One-shot LLM chart generation was landing around 60% visual quality in our tests. Two VLM iterations got us past 85%.

The analysis is chained instead of parallel. Chart 5 references Chart 1. Chart 8 disagrees with Chart 6 and says why. You can feel the difference when you read it.

Stack: a three-layer Snowflake warehouse (RAW → STAGING → ANALYTICS), five data loaders, eleven dbt models, Airflow for orchestration, Snowflake Cortex for in-warehouse LLM/VLM calls, and AWS Bedrock for RAG over SEC filings plus content guardrails.

We ran a blind benchmark where Gemini scored AAPL reports from FinSage, GPT-4o, o3, and Claude Opus 4.7 with identifying info stripped. FinSage came in at 8.1/10, beating both ChatGPT variants. Opus 4.7 won at 8.7 on free-form depth. Fair — it's a frontier model, and that's what it's good at. The catch is that Opus hands you one artifact. FinSage gives you 50 tickers on demand, daily-fresh data, a React dashboard, and a Q&A layer on top.

Built with Ojas Misra and Shrirangesh Vedanarayanan, who made this semester the kind of timeline I'll actually remember. A lot of the product decisions came out of side conversations with finance analysts they pulled in, and a lot of the late nights were just the three of us arguing about whether a chart was actually saying something.

A real thanks to Professor Kishore Aradhya and our TA Rithik. The decisions that ended up mattering most in this project trace back to conversations with them about how to frame the problem. The guest lectures were the other half of the course for me — Joe Reis, Vinay Narayana, Jane Urban, and others walked us through how data actually gets handled inside their companies, and more than a few ideas in FinSage came out of notes I was scribbling during those sessions.

Five years of full stack work, and this project finally put a name on something I'd been circling during my MIS program. AI engineering isn't prompt engineering. Most of the work is upstream of the model — the pipelines, the warehouse, the evals that tell you whether the thing is even correct. The LLM is the last 10%.

#DataEngineering #AIEngineering #Snowflake #Northeastern
