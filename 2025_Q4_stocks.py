# 2025 Q4 Stocks
from ctypes import sizeof
import yfinance as yf
import pandas as pd
from datetime import datetime as dt
from IPython.display import display, HTML
import plotly.graph_objects as go


# Define a class to represent each user
class Investor:
    def __init__(self, name, ticker, ticker_name, buy_price, dividend, image_url=None):
        self.name = name
        self.ticker = ticker
        self.ticker_name = ticker_name
        self.buy_price = buy_price
        self.dividend = dividend
        self.stock_data = None
        self.close_return = None
        # Set the image URL, with a default if none is provided
        self.image_url = image_url or "https://napha.no/multimedia/11733/ole-greger-lillevik_foto_rvts-nord.jpg?width=770"


# Define the start and end dates for data retrieval
start_date = "2025-09-15"
end_date = "2025-12-31"

# Create a list of investors
investors = [
    Investor("Årøen", "MOBA.OL", "MOBA", 14.65, 0.0, "https://media.licdn.com/dms/image/v2/C4D03AQGwLInyN_eEJA/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1516772708860?e=1756944000&v=beta&t=tXRIyBD88EEJZxvFGYIL5rZmJOt1u2RqmzmudWdton0"),
    Investor("Jack", "DOFGO.OL", "DOFGO", 98.70, 0.0, "https://media.licdn.com/dms/image/v2/C4D03AQFM46i7b4yZHg/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1517243795302?e=1756944000&v=beta&t=AYKCPxyfQAoc-IhB-XUDdjNYVqEp-WQbfx0k0aMSKeQ"),
    Investor("Tord", "BTC-USD", "BTC-USD", 114300.12, 0.0, "https://media.licdn.com/dms/image/v2/C5603AQHGsqTU03h-HQ/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1529667610143?e=1756944000&v=beta&t=lEIPnZ0WwI3eICoNvkr40Hz6OiU4T95VSPHBu4FlSoc"),
    Investor("Jan", "ETH-USD", "ETH-USD", 4188.41, 0.0, "https://media.licdn.com/dms/image/v2/D4D03AQFW7hYMR-qc9A/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1681576989752?e=1756944000&v=beta&t=ouVc-73zf-yS_pD7kfJ93SdODZ9GANGTvrt3fO1X0Nc"),
    Investor("Ness", "MP", "MP", 67.85, 0.0, "https://media.licdn.com/dms/image/v2/C4D03AQGDykuWUctUqg/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1617717541219?e=1756944000&v=beta&t=8t8qdEo66uLZpTP2HhrmijpOeHDScsNl5dXHswTWMAg"),
    Investor("Dr. S", "0P00000MVB.IR", "DNB TekA", 6106.50, 0.0, "https://media.licdn.com/dms/image/v2/C4E03AQH_niCGfGDPhw/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1517403047598?e=1756944000&v=beta&t=9RMmKK_Jv7TersXUN61rSkupopEdCj1RTE6g5TDFhP8"),
    Investor("Nøkleby", "LINK-USD", "LINK-USD", 22.12159, 0.0, "https://media.licdn.com/dms/image/v2/C4D03AQGMQ85dwKQ5oA/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1516581241868?e=1756944000&v=beta&t=6H5SFRkR_n3Clj-UOLdvYm5D2A69OdrdsPVNd9BGXqk"),
    Investor("Ole", "MU", "MU", 165.5, 0.0, "https://media.licdn.com/dms/image/v2/C4D03AQGzdJ__5WIjsA/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1517279675094?e=1756944000&v=beta&t=8fGC3-nOlINP_jkwplNwivm1RMgpfWJBoEgC_31xLgk"),
    Investor("Henrik", "ATO.PA", "ATO", 46.65, 0.0, "https://media.licdn.com/dms/image/v2/C4D03AQEPK2IOXzJ2XA/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1516586711850?e=1756944000&v=beta&t=2pi8BakVD78NDT5wnDEBu5-cmmkhwb3Fhob0buwnixE"),
    Investor("Nichlas", "MAS.OL", "MAS", 26.40, 0.0, "https://media.licdn.com/dms/image/v2/C4E03AQFjM7ENCRH0QQ/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1517471862479?e=1756944000&v=beta&t=QXl5kTBrDijE7qiqxQO0smeFL-vlKDlL85I4QWM6ROE"),
    Investor("Fredrik", "OSEBX.OL", "OSEBX", 1650.00, 0.0, "https://media.licdn.com/dms/image/v2/D4D03AQETpquIYxnspQ/profile-displayphoto-shrink_800_800/B4DZZfDM4aGwAk-/0/1745351397733?e=1756944000&v=beta&t=IfhLWIWR1edifO1hN8HYDqup1_5jrWSgS7gm6Bxgt4k"),
    Investor("OSEBX", "OSEBX.OL", "OSEBX", 1650.00, 0.0, "https://media.snl.no/media/52523/standard_compressed_Boersbygningen-3.jpg")
]

# Download USD/NOK exchange rate
usd_nok = yf.download("NOK=X", start=start_date)

# Download stock data for each investor
for investor in investors:
    investor.stock_data = yf.download(investor.ticker, start=start_date)

# Calculate close return for each investor
for investor in investors:
    investor.close_return = (
        investor.stock_data["Close"].div(investor.buy_price - investor.dividend).mul(100.0) - 100
    )

# Create a Plotly figure
fig = go.Figure()

# Plot the closing price data for each stock as a line chart
for investor in investors:
    series = pd.Series(data=investor.close_return.values.flatten(), index=investor.close_return.index)
    # Plot the data as lines
    fig.add_trace(go.Scatter(
        x=series.index,
        y=series.values,
        mode='lines',  # This ensures it's a line chart
        name=f"{investor.ticker_name} ({investor.name})"
    ))

# Update layout with title and labels
fig.update_layout(
    title="Q4 Stocks Index",
    xaxis_title="Date",
    yaxis_title="Return",
    legend_title="Stocks",
    template="plotly_dark",  # Optional: Use a dark theme for the plot
    xaxis=dict(
        tickformat="%Y-%m-%d",  # Format dates correctly
        tickangle=-45,  # Rotate ticks for readability
    ),
)

# Show the plot
# fig.show()
fig_html = fig.to_html(full_html=True)

# Collect data into a DataFrame
data = []
for investor in investors:
    close_price = investor.stock_data['Close'].iloc[-1].iat[-1]
    return_percentage = investor.close_return.iloc[-1].iat[-1]  # Calculate return percentage
    data.append({
        "Rank": f"<img src='{investor.image_url}' class=\"hover-img\">",
        "Investor": investor.name,
        "Ticker": investor.ticker_name,
        "Buy Price": f"{investor.buy_price:.3f}",
        "Dividend": f"{investor.dividend:.3f}",
        "Close Price": f"{close_price:.3f}",
        "Return[%]": f"{return_percentage:.2f}%"
    })

# Convert to DataFrame and sort by Return[%]
df = pd.DataFrame(data)
df["Return[%]"] = df["Return[%]"].str.rstrip('%').astype(float)
df = df.sort_values(by="Return[%]", ascending=False)

# Convert back to HTML
df["Return[%]"] = df["Return[%]"].astype(str) + "%"
html_table = df.to_html(escape=False, index=False)

# Get current date and time
now = dt.now()
# Format as a string
formatted_datetime = now.strftime("%Y-%m-%d %H:%M:%S")

# Combine the Plotly figure and the table into one HTML page
html_content = f"""
<html>
<head>
    <title>Investor Portfolio and Returns</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #121212;  /* Dark background */
            color: white;  /* White text for contrast */
            display: flex;
            flex-direction: column;
            align-items: center;
            margin: 0;
            padding: 0;
        }}
        .table-container {{
            width: 90%;
            margin-right: 20px;
            height: 100%;
            overflow-y: auto;
        }}
        .graph-container {{
            width: 90%;
            text-align: center;
            height: 100%;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            border-radius: 10px; /* Add rounded corners to the table */
            overflow: hidden; /* Ensures the corners are rounded properly */
            background-color: #333333;  /* Dark table background */
            color: white;
        }}
        th, td {{
            border: 1px solid #444444;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: orange;
            color: black;  /* Black text for table headers */
        }}
        td {{
            background-color: #222222;
        }}
        tr:hover {{
            background-color: #444444;  /* Row hover effect */
        }}
        td:hover {{
            background-color: #555555;  /* Cell hover effect */
            cursor: pointer;
        }}
        h1 {{
            margin-left: 20px;
            text-align: left;
        }}
        .hover-img {{
            width: 20px;
            height: 20px;
            cursor: pointer;
            transition: opacity 0.3s;
            border-radius: 2px; /* Add rounded corners to the table */
        }}
        .quote-container {{
            display: flex;
            justify-content: space-between;
            margin-left: 20px;
            width: 90%;
            background-color: rgba(0, 0, 0, 0.8);
            color: white;
            font-size: 1.2rem; /* Smaller font size */
            text-align: center;
            padding: 10px;
            white-space: nowrap;
            overflow: hidden;
            position: relative;
            z-index: 1;
            border-radius: 10px; /* Add rounded corners to the table */
            font-style: italic;
        }}
    </style>
</head>
<body>
    <h1>2025 Q4 Stocks Index</h1>
    <p>{formatted_datetime}</p>
    <div class="quote-container">
        <div id="quoteText">
            <!-- Quotes will be inserted here -->
        </div>
    </div>
    <div class="graph-container">
        <div>{fig_html}</div>
    </div>
    <div class="table-container">
        <div>{html_table}</div>
    </div>
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
                    const quotes = [
"Investing with friends is like playing poker — the stakes are high, but the rewards can be greater when you play smart.",
"In the stock market, competition is the game, but knowledge is the ultimate currency.",
"The best way to beat the market is to challenge it with a solid strategy and a bit of friendly rivalry.",
"A good friend helps you learn, but a great friend pushes you to invest smarter.",
"In stocks, the real victory isn’t in beating your friends, but in helping each other grow.",
"We’re not just investing money; we’re investing in each other’s success.",
"The stock market is a game where the only real competition is the market itself.",
"Competing for the best returns? Remember, the journey is just as valuable as the profit.",
"The higher the risk, the higher the reward — but let’s take calculated steps together.",
"Friendship is the best hedge against fear in the stock market.",
"The market doesn’t care about your emotions, but with friends by your side, you’ll always have support.",
"When we compete for returns, we’re really learning from each other.",
"The best investments are the ones that help us grow — financially and as friends.",
"Stocks are competitive, but integrity in investing is priceless.",
"Let’s challenge each other, not just to beat the market, but to beat our own expectations.",
"In a world of volatility, it’s the steady hand of a friend that keeps us grounded.",
"In investing, as in life, it’s not about the win — it’s about how you play the game together.",
"Let’s push each other to take smarter risks and reap the biggest rewards.",
"The market is unpredictable, but our commitment to success isn’t.",
"You might compete for returns, but the real wealth comes from shared knowledge.",
"Friends who invest together, thrive together.",
"It’s not about being the fastest to sell; it’s about being the smartest to buy.",
"Let’s see who can outsmart the market — but remember, we win together.",
"A competitive spirit is good, but collaboration leads to exponential growth.",
"In the stock market, it’s not the size of your portfolio, but the quality of your strategy that counts.",
"The key to success is knowing when to take risks, and when to let your friends take the lead.",
"Investing in stocks is tough, but it’s easier with a friend who shares the same goal.",
"Let’s make the market fear us with our collective knowledge and strategy.",
"The greatest investment you can make is in your own growth — and doing it with friends makes it even sweeter.",
"To beat the market, we must learn from each other’s victories and losses.",
"In the stock market, success is measured by how well you handle risk — and who’s beside you when you do.",
"We’re not competing for returns; we’re competing for excellence in investing.",
"Stocks may go up and down, but true friendship in investing remains a steady foundation.",
"The highest returns come when we combine our strengths and share insights.",
"Competitiveness is healthy — but let’s make sure we’re learning as much as we’re earning.",
"A great investment is one that pays dividends both in dollars and in wisdom.",
"Together, we can make the market a game we play to win.",
"The stock market rewards those who are patient, and friends who invest together are more likely to be patient.",
"Success in investing isn’t just about getting the highest return — it’s about sharing the knowledge you gain.",
"While we compete for returns, let’s remember the power of collaboration and learning together.",
"It’s not about timing the market — it’s about investing in the right strategies with the right friends.",
"The best returns come when we balance competition with cooperation.",
"Friends who invest together often find the highest returns in their mutual knowledge and trust.",
"In the world of stocks, it’s not the competition that makes us stronger, but the camaraderie.",
"In the stock market, we may be rivals, but in life, we’re partners in success.",
"The key to winning in stocks is not how fast you move, but how smart you invest.",
"Success isn’t about one of us winning the race, it’s about all of us crossing the finish line together.",
"Investing with friends brings out the best strategies — it’s a game of skill, not luck.",
"The highest returns aren’t always in numbers — they’re in the bonds we create through our investments.",
"In stocks and in life, it’s not about who gets the highest return, but who gets the most value out of the journey.",
                // POET Technologies Fun Facts
"POET Technologies is a pioneer in the field of photonics, revolutionizing data centers, telecoms, and sensing technologies.",
"Did you know POET Technologies is a leader in silicon photonics, combining the speed of light with the cost-effectiveness of silicon?",
"POET Technologies operates globally, from Canada to the US, and is making waves in the tech sector with innovative photonic solutions.",
"The company’s acquisition of DenseLight Semiconductors marked a new era in their quest for cutting-edge photonics technology.",
"POET Technologies specializes in using light to transmit data at incredibly fast speeds — making communication lightning fast!",
"Through partnerships with tech giants, POET Technologies is helping to advance the next generation of communication and data solutions.",
"Not just a photonics company, POET Technologies is also exploring applications in AI, artificial intelligence, and next-gen computing technologies.",
"Sustainability is at the heart of POET Technologies, with products designed to increase efficiency and reduce energy consumption.",
"With POET Technologies, data transfer is moving faster than ever, thanks to their innovative use of silicon photonics.",
"POET Technologies is more than just a tech company — they’re shaping the future of communications and computing with their groundbreaking solutions.",
"Their work with silicon photonics is essential for high-speed, low-cost data transmission, making them a game-changer in the tech world."
            ];
        let currentQuoteIndex = 0;
            // Function to display the current quote
            function changeQuote() {{
                const quoteTextElement = document.getElementById('quoteText');
                const randomIndex = Math.floor(Math.random() * quotes.length);
                quoteTextElement.textContent = quotes[randomIndex];
            }}
            // Initial call to display the first quote
            changeQuote();
            // Change the quote every 5 seconds
            setInterval(changeQuote, 5000);
        }});
    </script>
</body>
</html>
"""

display(HTML(html_content))

# with open("C:\\Users\\Jan.Aamnes\\OneDrive - insidemedia.net\\Documents\\Python\\Stocks\\index.html", "w", encoding="utf-8") as f:
#     f.write(html_content)
