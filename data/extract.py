import wikipediaapi
import json
import os

wiki = wikipediaapi.Wikipedia(
    language='en',
    user_agent='Lab19_TranMinhToan/1.0 (educational project)'
)

ai_companies = [
    "OpenAI", "Anthropic", "Google DeepMind", "Meta AI",
    "Mistral AI", "Cohere", "Hugging Face", "Stability AI",
    "Inflection AI", "xAI", "Adept AI", "Character.AI",
    "Runway ML", "Midjourney", "Scale AI", "DataRobot",
    "C3.ai", "Palantir Technologies", "UiPath", "Automation Anywhere",
    "Blue Prism", "NVIDIA", "Intel", "IBM", "Microsoft",
    "Amazon Web Services", "Google", "Apple Inc.", "Baidu", "Alibaba Group",
    "Tencent", "Samsung Electronics", "Sony", "LG Electronics", "Lenovo",
    "Salesforce", "Oracle Corporation", "SAP", "ServiceNow", "Workday",
    "Cognizant", "Infosys", "Wipro", "Accenture", "Capgemini",
    "Appen", "Lionbridge Technologies", "Defined.ai", "iMerit", "Samasource",
    "Clarifai", "Algorithmia", "H2O.ai", "Dataiku", "Domino Data Lab",
    "RapidMiner", "KNIME", "Alteryx", "Tableau Software", "MicroStrategy",
    "Veritone", "Evolent Health", "Tempus AI", "PathAI", "Recursion Pharmaceuticals",
    "Insilico Medicine", "BenevolentAI", "Exscientia", "Absci", "Generate Biomedicines",
    "Cerebras Systems", "SambaNova Systems", "Graphcore", "Groq", "Tenstorrent",
    "Lightmatter", "Mythic", "Rain Neuromorphics", "BrainChip Holdings", "Numenta",
    "DeepL", "Grammarly", "Jasper AI", "Copy.ai", "Writesonic",
    "Synthesia", "D-ID", "ElevenLabs", "Resemble AI", "Speechify",
    "Glean", "Notion", "Airtable", "Monday.com", "Asana",
    "Moveworks", "Otter.ai", "Fireflies.ai", "Chorus.ai", "Gong",
    "Darktrace", "CrowdStrike", "SentinelOne", "Vectra AI", "Cylance",
]

output_dir = os.path.dirname(os.path.abspath(__file__))
output_json = os.path.join(output_dir, "corpus.json")
output_txt_dir = os.path.join(output_dir, "articles")
os.makedirs(output_txt_dir, exist_ok=True)

corpus = []
skipped = []

for i, company in enumerate(ai_companies):
    print(f"[{i+1}/{len(ai_companies)}] Fetching: {company}")
    page = wiki.page(company)
    if page.exists():
        entry = {"title": company, "text": page.text}
        corpus.append(entry)
        safe_name = company.replace("/", "_").replace(" ", "_")
        txt_path = os.path.join(output_txt_dir, f"{safe_name}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"# {company}\n\n{page.text}")
    else:
        print(f"  [SKIP] Page not found: {company}")
        skipped.append(company)

with open(output_json, "w", encoding="utf-8") as f:
    json.dump(corpus, f, ensure_ascii=False, indent=2)

print(f"\nDone! Saved {len(corpus)} articles to '{output_json}' and '{output_txt_dir}/'")
if skipped:
    print(f"Skipped ({len(skipped)}): {skipped}")