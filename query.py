from flask import Flask, request, render_template_string
import pandas as pd
import numpy as np
import re

app = Flask(__name__)

# Load data
data = pd.read_csv('merged_crop_rainfall.csv')

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Project Samarth</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        h1 { color: #2c3e50; }
        form { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        input[type="text"] { padding: 10px; border: 2px solid #ddd; border-radius: 4px; font-size: 16px; }
        button { padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #2980b9; }
        .answer { background: white; padding: 20px; margin-top: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); white-space: pre-wrap; font-family: monospace; }
        .query-separator { margin: 30px 0; border-top: 3px double #3498db; padding-top: 20px; }
    </style>
</head>
<body>
    <h1>🌾 Project Samarth – Multi-Query Agricultural Engine</h1>
    <form method="POST">
        <input type="text" name="question" placeholder="Ask multiple questions! (e.g., 'Highest rice production AND rainfall in Punjab')" size="70" required>
        <button type="submit">🔍 Ask</button>
    </form>
    {% if answer %}
    <div class="answer">{{ answer }}</div>
    {% endif %}
</body>
</html>
"""


# ============= QUERY SPLITTING ENGINE =============

def split_compound_query(question):
    """Split a compound question into multiple sub-queries with context preservation"""
    question_lower = question.lower()

    # Check if asking about data source - handle separately
    asks_source = any(phrase in question_lower for phrase in [
        'where', 'data came from', 'source', 'from where', 'data source'
    ])

    # If asking about source, split it out as a separate query
    source_query = None
    main_question = question

    if asks_source:
        # Extract the source question part
        source_patterns = [
            r'(and\s+)?(also\s+)?mention\s+where.*',
            r'(and\s+)?(also\s+)?where.*came\s+from',
            r'(and\s+)?(also\s+)?what.*source',
        ]

        for pattern in source_patterns:
            match = re.search(pattern, question_lower)
            if match:
                source_query = "where does the data come from"
                main_question = question[:match.start()].strip()
                break

    # Now check if the main question has multiple distinct queries
    # Be conservative - only split on clear separators when queries are actually independent

    # Pattern 1: "Do X. Then do Y" or "Do X; do Y" (clear independent queries)
    if re.search(r'\.\s+[A-Z]', main_question) or ';' in main_question:
        queries = re.split(r'[.;]\s+', main_question)
        queries = [q.strip() for q in queries if q.strip()]

    # Pattern 2: Look for "at the same time" - this indicates ONE compound query, not multiple
    elif 'at the same time' in question_lower:
        queries = [main_question]

    # Pattern 3: "and also" or "also" at sentence level (but NOT within a comparison)
    elif re.search(r'\.\s+(and\s+)?also\s+', question_lower):
        queries = re.split(r'\.\s+(and\s+)?also\s+', main_question)
        queries = [q.strip() for q in queries if q.strip() and len(q) > 3]

    else:
        # Single query - keep it together
        queries = [main_question]

    # Add source query at the end if it was found
    if source_query:
        queries.append(source_query)

    return queries


# ============= QUERY PROCESSING ENGINE =============

def parse_query(question):
    """Parse natural language question and extract intent"""
    question_lower = question.lower()

    # Extract state names
    states = data['State'].unique()
    mentioned_states = [s for s in states if s.lower() in question_lower]

    # Extract crop names
    crops = data['crop'].unique()
    mentioned_crops = [c for c in crops if c.lower() in question_lower]

    # Extract years
    years = re.findall(r'\b(20\d{2}|\d{4})\b', question)
    years = [int(y) for y in years if int(y) in data['Year'].unique()]

    # Check for data source query
    if any(phrase in question_lower for phrase in ['source', 'data came from', 'where', 'from where']):
        return {
            'type': 'source',
            'states': mentioned_states,
            'crops': mentioned_crops,
            'years': years if years else None,
            'metric': None
        }

    # Determine query type
    query_type = None

    if any(word in question_lower for word in ['highest', 'maximum', 'most', 'top', 'largest', 'best']):
        query_type = 'highest'
    elif any(word in question_lower for word in ['lowest', 'minimum', 'least', 'smallest', 'worst']):
        query_type = 'lowest'
    elif any(word in question_lower for word in ['compare', 'comparison', 'versus', 'vs', 'difference', 'between']):
        query_type = 'compare'
    elif any(word in question_lower for word in ['average', 'mean', 'avg']):
        query_type = 'average'
    elif any(word in question_lower for word in ['total', 'sum', 'overall']):
        query_type = 'total'
    elif any(word in question_lower for word in
             ['trend', 'over time', 'yearly', 'year by year', 'every year', 'each year', 'growth']):
        query_type = 'trend'
    elif any(word in question_lower for word in ['correlation', 'relation', 'affect', 'impact', 'depend']):
        query_type = 'correlation'
    elif any(word in question_lower for word in ['list', 'show all', 'what are']):
        query_type = 'list'
    else:
        query_type = 'general'

    # Determine primary metric(s)
    asks_rainfall = any(word in question_lower for word in ['rainfall', 'rain', 'precipitation'])
    asks_production = any(word in question_lower for word in ['production', 'produce', 'crop', 'yield'])
    asks_both = 'at the same time' in question_lower or 'also' in question_lower

    # Determine metric
    if asks_both or (asks_rainfall and asks_production):
        metric = 'Both'  # Special flag for queries asking about both
    elif asks_rainfall:
        metric = 'Rainfall'
    else:
        metric = 'Production'

    return {
        'type': query_type,
        'states': mentioned_states,
        'crops': mentioned_crops,
        'years': years if years else None,
        'metric': metric,
        'asks_both': asks_both or (asks_rainfall and asks_production)
    }


def format_number(num):
    """Format large numbers with commas"""
    return f"{num:,.2f}"


def query_source(params):
    """Answer questions about data source"""
    answer = f"╔═══════════════════════════════════════════════════════════╗\n"
    answer += f"║  DATA SOURCE INFORMATION\n"
    answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

    answer += "🌐 PRIMARY SOURCE:\n"
    answer += "═" * 63 + "\n"
    answer += "  Portal: data.gov.in\n"
    answer += "  Official: Open Government Data (OGD) Platform India\n"
    answer += "  Website: https://data.gov.in\n\n"

    answer += "📁 Dataset: merged_crop_rainfall.csv\n\n"
    answer += "📊 Data Contents:\n"
    answer += f"  • Years Covered: {data['Year'].min()} - {data['Year'].max()}\n"
    answer += f"  • States: {data['State'].nunique()} Indian states\n"
    answer += f"  • Crops: {data['crop'].nunique()} different crop types\n"
    answer += f"  • Total Records: {len(data):,}\n\n"

    answer += "🔍 Data Fields:\n"
    answer += "  • State: Geographic location\n"
    answer += "  • Year: Time period (2009-2013)\n"
    answer += "  • Crop: Agricultural product\n"
    answer += "  • Production: Output quantity\n"
    answer += "  • Rainfall: Precipitation in millimeters\n\n"

    answer += "ℹ️  NOTE:\n"
    answer += "   This is a merged dataset combining agricultural production\n"
    answer += "   data with regional rainfall measurements from data.gov.in,\n"
    answer += "   India's official open data portal maintained by the\n"
    answer += "   National Informatics Centre (NIC).\n"

    return answer


def query_highest(params):
    """Find highest production/rainfall"""
    df = data.copy()

    if params['crops']:
        df = df[df['crop'].isin(params['crops'])]
    if params['years']:
        df = df[df['Year'].isin(params['years'])]
    if params['states']:
        df = df[df['State'].isin(params['states'])]

    metric = params['metric'] if params['metric'] != 'Both' else 'Production'
    result = df.groupby('State')[metric].sum().sort_values(ascending=False)

    top_state = result.index[0]
    top_value = result.iloc[0]

    answer = f"╔═══════════════════════════════════════════════════════════╗\n"
    answer += f"║  HIGHEST {metric.upper()} ANALYSIS\n"
    answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

    answer += f"🏆 TOP STATE: {top_state}\n"
    answer += f"📊 {metric}: {format_number(top_value)}"
    if metric == 'Rainfall':
        answer += " mm"
    answer += "\n\n"

    answer += "TOP 5 RANKING:\n"
    answer += "═" * 63 + "\n"
    for i, (state, value) in enumerate(result.head(5).items(), 1):
        answer += f"  {i}. {state:25} → {format_number(value)}"
        if metric == 'Rainfall':
            answer += " mm"
        answer += "\n"

    return answer


def query_lowest(params):
    """Find lowest production/rainfall"""
    df = data.copy()

    if params['crops']:
        df = df[df['crop'].isin(params['crops'])]
    if params['years']:
        df = df[df['Year'].isin(params['years'])]
    if params['states']:
        df = df[df['State'].isin(params['states'])]

    metric = params['metric'] if params['metric'] != 'Both' else 'Production'
    result = df.groupby('State')[metric].sum().sort_values(ascending=True)

    bottom_state = result.index[0]
    bottom_value = result.iloc[0]

    answer = f"╔═══════════════════════════════════════════════════════════╗\n"
    answer += f"║  LOWEST {metric.upper()} ANALYSIS\n"
    answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

    answer += f"📉 BOTTOM STATE: {bottom_state}\n"
    answer += f"📊 {metric}: {format_number(bottom_value)}"
    if metric == 'Rainfall':
        answer += " mm"
    answer += "\n\n"

    answer += "BOTTOM 5 RANKING:\n"
    answer += "═" * 63 + "\n"
    for i, (state, value) in enumerate(result.head(5).items(), 1):
        answer += f"  {i}. {state:25} → {format_number(value)}"
        if metric == 'Rainfall':
            answer += " mm"
        answer += "\n"

    return answer


def query_compare(params):
    """Compare production/rainfall between states - handles compound queries"""
    if len(params['states']) < 2:
        return "❌ Please mention at least 2 states to compare"

    df = data.copy()

    if params['crops']:
        df = df[df['crop'].isin(params['crops'])]
    if params['years']:
        df = df[df['Year'].isin(params['years'])]

    state1, state2 = params['states'][0], params['states'][1]

    # Check if this is asking for both rainfall AND production
    if params.get('asks_both') or params['metric'] == 'Both':
        # Handle compound comparison
        answer = f"╔═══════════════════════════════════════════════════════════╗\n"
        answer += f"║  COMPREHENSIVE COMPARISON: {state1.upper()} vs {state2.upper()}\n"
        answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

        # PART 1: Rainfall comparison
        answer += "🌧️  RAINFALL COMPARISON:\n"
        answer += "═" * 63 + "\n\n"

        df1 = df[df['State'] == state1]
        df2 = df[df['State'] == state2]

        # Year by year rainfall
        years = sorted(df['Year'].unique())
        answer += f"{'Year':<10} {state1:<25} {state2:<25}\n"
        answer += "-" * 63 + "\n"

        for year in years:
            rain1 = df1[df1['Year'] == year]['Rainfall'].mean()
            rain2 = df2[df2['Year'] == year]['Rainfall'].mean()
            answer += f"{year:<10} {format_number(rain1) + ' mm':<25} {format_number(rain2) + ' mm':<25}\n"

        avg_rain1 = df1['Rainfall'].mean()
        avg_rain2 = df2['Rainfall'].mean()
        answer += "-" * 63 + "\n"
        answer += f"{'Average':<10} {format_number(avg_rain1) + ' mm':<25} {format_number(avg_rain2) + ' mm':<25}\n"

        # PART 2: Top crop production
        answer += "\n\n🌾 TOP CROPS PRODUCED:\n"
        answer += "═" * 63 + "\n\n"

        for state in [state1, state2]:
            state_df = df[df['State'] == state]
            top_crops = state_df.groupby('crop')['Production'].sum().sort_values(ascending=False).head(5)

            answer += f"📍 {state.upper()}:\n"
            for i, (crop, prod) in enumerate(top_crops.items(), 1):
                answer += f"  {i}. {crop:20} → {format_number(prod)}\n"
            answer += "\n"

        return answer

    else:
        # Single metric comparison (original logic)
        metric = params['metric'] if params['metric'] != 'Both' else 'Production'

        df1 = df[df['State'] == state1]
        df2 = df[df['State'] == state2]

        if metric == 'Rainfall':
            value1 = df1['Rainfall'].mean()
            value2 = df2['Rainfall'].mean()
        else:
            value1 = df1[metric].sum()
            value2 = df2[metric].sum()

        answer = f"╔═══════════════════════════════════════════════════════════╗\n"
        answer += f"║  COMPARISON: {state1.upper()} vs {state2.upper()}\n"
        answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

        answer += f"📊 {metric.upper()} COMPARISON:\n\n"
        answer += f"  {state1:25} → {format_number(value1)}"
        if metric == 'Rainfall':
            answer += " mm (avg)"
        answer += "\n"
        answer += f"  {state2:25} → {format_number(value2)}"
        if metric == 'Rainfall':
            answer += " mm (avg)"
        answer += "\n\n"

        diff = abs(value1 - value2)
        percent_diff = (diff / min(value1, value2)) * 100
        winner = state1 if value1 > value2 else state2

        answer += f"  Difference: {format_number(diff)}"
        if metric == 'Rainfall':
            answer += " mm"
        answer += f"\n  Percentage: {percent_diff:.2f}%\n"
        answer += f"  Winner: {winner} 🏆\n"

        return answer


def query_trend(params):
    """Show trend over years"""
    df = data.copy()

    if params['crops']:
        df = df[df['crop'].isin(params['crops'])]
    if params['states']:
        df = df[df['State'].isin(params['states'])]

    metric = params['metric'] if params['metric'] != 'Both' else 'Production'
    trend = df.groupby('Year')[metric].sum().sort_index()

    answer = f"╔═══════════════════════════════════════════════════════════╗\n"
    answer += f"║  {metric.upper()} TREND (2009-2013)\n"
    answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

    for year, value in trend.items():
        answer += f"  {year}  →  {format_number(value)}"
        if metric == 'Rainfall':
            answer += " mm"
        answer += "\n"

    first_val = trend.iloc[0]
    last_val = trend.iloc[-1]
    growth = ((last_val - first_val) / first_val) * 100

    answer += f"\n  Overall Growth: {growth:+.2f}%\n"
    answer += f"  Trend: {'📈 Increasing' if growth > 0 else '📉 Decreasing'}\n"

    return answer


def query_list(params):
    """List items based on query"""
    df = data.copy()

    if params['states']:
        df = df[df['State'].isin(params['states'])]
    if params['years']:
        df = df[df['Year'].isin(params['years'])]

    answer = f"╔═══════════════════════════════════════════════════════════╗\n"
    answer += f"║  TOP CROPS BY STATE\n"
    answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

    for state in params['states'] if params['states'] else df['State'].unique()[:5]:
        state_df = df[df['State'] == state]
        top_crops = state_df.groupby('crop')['Production'].sum().sort_values(ascending=False).head(5)

        answer += f"📍 {state.upper()}:\n"
        for i, (crop, prod) in enumerate(top_crops.items(), 1):
            answer += f"  {i}. {crop:20} → {format_number(prod)}\n"
        answer += "\n"

    return answer


def query_general(params):
    """Handle general queries"""
    df = data.copy()

    if params['crops']:
        df = df[df['crop'].isin(params['crops'])]
    if params['states']:
        df = df[df['State'].isin(params['states'])]
    if params['years']:
        df = df[df['Year'].isin(params['years'])]

    answer = f"╔═══════════════════════════════════════════════════════════╗\n"
    answer += f"║  DATA SUMMARY\n"
    answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

    answer += f"  Total Records:    {len(df)}\n"
    answer += f"  Total Production: {format_number(df['Production'].sum())}\n"
    answer += f"  Avg Rainfall:     {format_number(df['Rainfall'].mean())} mm\n"
    answer += f"  States:           {df['State'].nunique()}\n"
    answer += f"  Crops:            {df['crop'].nunique()}\n"

    return answer


def process_single_query(question):
    """Process a single query and return the answer"""
    try:
        params = parse_query(question)

        if params['type'] == 'source':
            return query_source(params)
        elif params['type'] == 'highest':
            return query_highest(params)
        elif params['type'] == 'lowest':
            return query_lowest(params)
        elif params['type'] == 'compare':
            return query_compare(params)
        elif params['type'] == 'trend':
            return query_trend(params)
        elif params['type'] == 'list':
            return query_list(params)
        else:
            return query_general(params)

    except Exception as e:
        return f"❌ Error: {str(e)}"


# ============= MAIN ROUTE =============

@app.route('/', methods=['GET', 'POST'])
def index():
    answer = None

    if request.method == 'POST':
        question = request.form.get('question', '').strip()

        if not question:
            answer = "❌ Please enter a question!"
        else:
            try:
                # Split compound queries
                queries = split_compound_query(question)

                if len(queries) == 1:
                    # Single query (possibly compound, handled by individual functions)
                    answer = process_single_query(queries[0])
                else:
                    # Multiple truly independent queries
                    answer = f"╔═══════════════════════════════════════════════════════════╗\n"
                    answer += f"║  MULTI-QUERY RESPONSE ({len(queries)} questions detected)\n"
                    answer += f"╚═══════════════════════════════════════════════════════════╝\n\n"

                    for i, q in enumerate(queries, 1):
                        answer += f"\n{'=' * 63}\n"
                        answer += f"QUERY {i}: {q}\n"
                        answer += f"{'=' * 63}\n\n"

                        sub_answer = process_single_query(q)
                        answer += sub_answer + "\n"

            except Exception as e:
                answer = f"❌ Error: {str(e)}\n\nTry rephrasing your question."

    return render_template_string(HTML_TEMPLATE, answer=answer)


if __name__ == '__main__':
    print("=" * 60)
    print("🌾 Project Samarth - Smart Multi-Query Engine")
    print("=" * 60)
    print(f"📊 Data: {len(data)} records")
    print(f"📅 Years: {data['Year'].min()}-{data['Year'].max()}")
    print("=" * 60)
    print("🚀 Server: http://localhost:5000")
    print("=" * 60)
    print("\n📝 Try Complex Queries:")
    print("  • Compare rainfall in Rajasthan and Maharashtra every year")
    print("    At the same time list top crops and mention data source")
    print("  • Highest rice production. Also show trend")
    print("=" * 60)
    app.run(debug=True, port=5000)