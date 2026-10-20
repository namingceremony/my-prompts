1. Start the API (window 1, keep it open)


cd "<SOP-RAG folder>"
.\.venv\Scripts\Activate.ps1
python run_claim_validator_api.py
It takes a minute or two to load. It's ready when http://127.0.0.1:8300/health shows "status": "ready".

2. Start the frontend (window 2, keep it open)


cd "<SOP-RAG folder>\validator-frontend"
npm install      # first time only
npm run dev
Then open http://localhost:5175.

3. Check a few claims in the web app

Click Sample IDs, pick an ORS ID (or type one from the holdout set), then click Look Up Claim.
Click Run Primary Model to see Model A's prediction and its probability of Rework.
Click Run GenAI Validation to see the final prediction, the reason, the checks, the SOP passages and the similar historical claims. When Model A predicts Rework, the GenAI step is skipped.
4. Several claims at once from the command line (window 3)


cd "<SOP-RAG folder>"
.\.venv\Scripts\Activate.ps1
python scripts\k24_batch_pipeline.py run --input holdout_test_2000_v36.csv --limit 10
$out = 'artifacts\claim_validator\batch\output\holdout_test_2000_v36_first10_output.csv'
Import-Csv $out | Format-Table ors_id, actual_label, primary_prediction, primary_probability_rework, validator_decision_path, final_prediction -AutoSize
Import-Csv $out | Format-List ors_id, final_prediction, final_reason
