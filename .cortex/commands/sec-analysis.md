---
description: Analyze SEC filings for a ticker with Bedrock KB verification
argument-hint: "<TICKER>"
---

# SEC Filing Analysis

Run SEC filing analysis for a ticker with pre-flight verification of data availability and Bedrock integration health.

## Steps

1. **Verify SEC data in Snowflake**:
   ```sql
   -- Check filing metadata
   SELECT FILING_TYPE, COUNT(*) AS FILINGS, MAX(FILING_DATE) AS LATEST
   FROM FINSAGE_DB.RAW.RAW_SEC_FILINGS
   WHERE TICKER = '$TICKER'
   GROUP BY FILING_TYPE
   ORDER BY LATEST DESC;

   -- Check extracted text availability
   SELECT COUNT(*) AS EXTRACTED_DOCS
   FROM FINSAGE_DB.RAW.RAW_SEC_FILING_TEXT
   WHERE TICKER = '$TICKER';

   -- Check analytics summary
   SELECT FILING_TYPE, PERIOD_END, FINANCIAL_HEALTH
   FROM FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
   WHERE TICKER = '$TICKER'
   ORDER BY PERIOD_END DESC
   LIMIT 5;
   ```

2. **Verify S3 filing documents**:
   ```python
   import boto3
   s3 = boto3.client("s3")

   # List available filings for ticker
   cik = CIK_MAPPING.get("$TICKER")
   response = s3.list_objects_v2(
       Bucket="finsage-sec-filings",
       Prefix=f"sec-filings/{cik}/",
       MaxKeys=20
   )
   print(f"Found {response.get('KeyCount', 0)} filing documents in S3")
   ```

3. **Verify Bedrock Knowledge Base health**:
   ```python
   import boto3
   bedrock_agent = boto3.client("bedrock-agent")

   # Check KB status
   kb = bedrock_agent.get_knowledge_base(knowledgeBaseId=KB_ID)
   print(f"KB Status: {kb['knowledgeBase']['status']}")

   # Test retrieval
   bedrock_runtime = boto3.client("bedrock-agent-runtime")
   test = bedrock_runtime.retrieve(
       knowledgeBaseId=KB_ID,
       retrievalQuery={"text": f"Latest financial results for $TICKER"},
       retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}}
   )
   print(f"Retrieved {len(test['retrievalResults'])} passages")
   ```

4. **Run analysis**:
   ```python
   from agents.analysis_agent import AnalysisAgent

   agent = AnalysisAgent()
   sec_analysis = agent.analyze_sec_filings("$TICKER")
   ```

5. **Validate output**:
   - [ ] Analysis text is non-empty
   - [ ] Financial health signal derived (EXCELLENT/HEALTHY/FAIR/UNPROFITABLE)
   - [ ] Key metrics extracted (Revenue, Net Income, etc.)
   - [ ] Guardrails did not block the analysis
   - [ ] Cross-ticker comparison available (if peer group exists)

6. **Check quality**:
   - Was RAG retrieval relevant? (check source passages)
   - Did guardrails flag any content? (check guardrail trace)
   - Is the analysis grounded in actual filing data? (verify numbers)
