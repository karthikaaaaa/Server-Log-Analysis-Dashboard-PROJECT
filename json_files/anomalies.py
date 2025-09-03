import streamlit as st  # type: ignore
import pandas as pd  # type: ignore
import plotly.express as px  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
from collections import Counter
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier  # type: ignore
from sklearn.model_selection import train_test_split  # type: ignore
from sklearn.preprocessing import OneHotEncoder  # type: ignore
import json
import os
import re

# Streamlit App
st.set_page_config(page_title="Log Analysis Dashboard", layout="wide", page_icon="📊")
st.title("📊 LogInsight: Retail and eCommerce web server log analysis dashboard for detecting anomalies")

# File paths
access_log_file = r"C:\PROJECT\json_files\s1_sample.json"
minute_metrics_file = r"C:\PROJECT\json_files\minute_metrics.json"
geo_db_path = r"C:\Users\saira\OneDrive\Documents\PROJECTS\json_files\GeoLite2-City.mmdb"


# Load JSON data
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                st.error(f"Error: {file_path} contains invalid JSON.")
                return []
    else:
        st.warning(f"File not found: {file_path}")
        return []

# Function to extract IP addresses from the log file
def extract_ips(access_log_file):
    with open(access_log_file, 'r') as file:
        log_data = file.read()
    # Regex to match IPv4 addresses
    ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    return re.findall(ip_pattern, log_data)

# Function to get geolocation for an IP
def get_geolocation(ip, reader):
    try:
        response = reader.city(ip)
        return {
            'ip': ip,
            'city': response.city.name,
            'country': response.country.name,
            'latitude': response.location.latitude,
            'longitude': response.location.longitude,
        }
    except geoip2.errors.AddressNotFoundError:
        return {'ip': ip, 'error': 'Address not found'}


# Function to calculate traffic metrics
def calculate_traffic_metrics(access_logs, aggregated_metrics):
    unique_visitors = set()
    http_methods = Counter()

    for log in access_logs:
        unique_visitors.add(log.get("ip"))
        http_methods[log.get("request", {}).get("method", "")] += 1

    if not aggregated_metrics:
        return {
            "max_rps": 0,
            "min_rps": 0,
            "unique_visitors": len(unique_visitors),
            "http_methods": http_methods,
        }

    max_rps = max(
        aggregated_metrics,
        key=lambda x: x.get("metrics", {}).get("total_requests", 0),
    ).get("metrics", {}).get("total_requests", 0) / 60
    min_rps = min(
        aggregated_metrics,
        key=lambda x: x.get("metrics", {}).get("total_requests", 0),
    ).get("metrics", {}).get("total_requests", 0) / 60

    return {
        "max_rps": max_rps,
        "min_rps": min_rps,
        "unique_visitors": len(unique_visitors),
        "http_methods": http_methods,
    }

# Main code
def main():
    # Extract IPs
    ip_addresses = extract_ips(access_log_file)

    # Load GeoLite2 database
    with geoip2.database.Reader(geo_db_path) as reader:
        for ip in ip_addresses:
            geo_info = get_geolocation(ip, reader)
            print(geo_info)


# Function to calculate response metrics
def calculate_response_metrics(access_logs):
    status_code_distribution = Counter()
    total_latency = 0
    latency_count = 0
    error_count = 0
    redirect_count = 0

    for log in access_logs:
        status_code = log.get("status_code", 0)
        status_code_distribution[status_code // 100] += 1
        if 400 <= status_code < 600:
            error_count += 1
        if 300 <= status_code < 400:
            redirect_count += 1

        request_time = log.get("request_time", 0)
        total_latency += request_time
        latency_count += 1

    average_latency = total_latency / latency_count if latency_count > 0 else 0
    error_rate = (error_count / len(access_logs)) * 100 if access_logs else 0
    redirect_rate = (redirect_count / len(access_logs)) * 100 if access_logs else 0

    return {
        "status_code_distribution": status_code_distribution,
        "average_latency": average_latency,
        "error_rate": error_rate,
        "redirect_rate": redirect_rate,
    }


# Function to parse user agent manually
def parse_user_agent(user_agent):
    # Regular expression patterns for parsing different parts of the user agent
    browser_pattern = r"(Chrome|Firefox|Safari|Edge|MSIE|Trident)/([\d\.]+)"
    device_pattern = r"\(([^;]+); ([^;]+);"
    bot_pattern = r"(Googlebot|Bingbot|Slurp|DuckDuckBot|Baiduspider)"

    # Parse browser
    browser_match = re.search(browser_pattern, user_agent)
    browser = browser_match.group(1) if browser_match else "Unknown Browser"
    browser_version = browser_match.group(2) if browser_match else "Unknown Version"

    # Parse device
    device_match = re.search(device_pattern, user_agent)
    device = device_match.group(2) if device_match else "Unknown Device"

    # Parse bot (if any)
    bot_match = re.search(bot_pattern, user_agent)
    is_bot = bool(bot_match)
    bot_family = bot_match.group(1) if bot_match else "No Bot"

    return {
        "browser": browser,
        "browser_version": browser_version,
        "device": device,
        "is_bot": is_bot,
        "bot_family": bot_family,
    }

# Function to categorize user agents manually
def categorize_user_agents(access_logs):
    browsers = Counter()
    devices = Counter()
    bots = Counter()

    for log in access_logs:
        user_agent = log.get("user_agent", "")
        parsed_ua = parse_user_agent(user_agent)
        
        # Check if the user-agent is a bot
        if parsed_ua["is_bot"]:
            bots[parsed_ua["bot_family"]] += 1
        else:
            # Record the browser and device
            browsers[parsed_ua["browser"]] += 1
            devices[parsed_ua["device"]] += 1

    return {
        "browsers": browsers,
        "devices": devices,
        "bots": bots
    }

# Function to calculate user behavior metrics
def calculate_user_behavior_metrics(access_logs):
    top_urls = Counter()
    user_agents = Counter()

    # Collecting the top URLs and user agents
    for log in access_logs:
        url = log.get("request", {}).get("resource", "")
        top_urls[url] += 1
        user_agent = log.get("user_agent", "")
        user_agents[user_agent] += 1

    # Categorize user agents into browsers, devices, and bots
    categorized_ua = categorize_user_agents(access_logs)

    return {
        "top_urls": top_urls.most_common(5),
        "user_agents": user_agents,
        "browsers": categorized_ua["browsers"],
        "devices": categorized_ua["devices"],
        "bots": categorized_ua["bots"]
    }



def calculate_security_metrics(access_logs):
    # Step 1: Parse logs into a DataFrame
    data = []
    for log in access_logs:
        data.append({
            "ip": log.get("ip"),
            "status_code": log.get("status_code", 0),
            "response_size": log.get("response_size", 0),
            "referer": log.get("referer", "-"),
            "user_agent": log.get("user_agent", ""),
            "url": log.get("request", {}).get("resource", ""),
            "response_time": log.get("request_time", 0),
        })
    
    df = pd.DataFrame(data)
    
    # Debug: Print the parsed DataFrame
    print("Parsed DataFrame:")
    print(df)
    
    if df.empty:
        return {"error": "No log data available"}
    
    # Step 2: Directly filter high latency and large response sizes
    high_latency_requests = df[df["response_time"] > 1][["ip", "url", "response_time"]].to_dict(orient='records')
    large_response_sizes = df[df["response_size"] > 1][["ip", "url", "response_size"]].to_dict(orient='records')
    
    # Debug: Print high latency and large response size logs
    print("High Latency Requests:")
    print(high_latency_requests)
    
    print("Large Response Sizes:")
    print(large_response_sizes)
    
    # Step 3: Define categorical and numerical features for anomaly detection
    categorical_features = ["ip", "referer", "user_agent", "url"]
    numerical_features = ["status_code", "response_size", "response_time"]
    
    # Step 4: One-hot encode categorical features
    encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
    encoded_features = encoder.fit_transform(df[categorical_features])
    feature_names = encoder.get_feature_names_out(categorical_features)
    df_encoded = pd.DataFrame(encoded_features, columns=feature_names)
    
    # Step 5: Merge encoded features with numerical data
    df_final = pd.concat([df_encoded, df[numerical_features]], axis=1)
    
    # Step 6: Define labels for training (1: Anomalous, 0: Normal)
    df_final["anomaly"] = ((df["status_code"].isin([403, 500, 503])) |
                             (df["response_size"] < 10) | (df["response_size"] > 1000) |
                             (df["response_time"] > 1) | (df["status_code"] == 401)).astype(int)
    
    # Debug: Print anomaly labels
    print("Anomaly Labels:")
    print(df_final["anomaly"].value_counts())
    
    # Step 7: Train Random Forest model
    X_train, X_test, y_train, y_test = train_test_split(df_final.drop("anomaly", axis=1), df_final["anomaly"], test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Step 8: Predict anomalies
    df["anomaly_score"] = model.predict(df_final.drop("anomaly", axis=1))
    
    # Debug: Print anomaly scores
    print("Anomaly Scores:")
    print(df[["ip", "url", "response_time", "response_size", "anomaly_score"]])
    
    # Step 9: Extract anomalies
    anomalies = df[df["anomaly_score"] == 1]
    
    # Debug: Print anomalies
    print("Anomalies:")
    print(anomalies)
    
    # Step 10: Return metrics
    return {
        "high_failure_ips": Counter(anomalies[anomalies["status_code"].isin([403, 500, 503])]["ip"]),
        "unusual_request_patterns": Counter(anomalies["url"]),
        "high_latency_requests": high_latency_requests,  # Directly filtered from df
        "unauthorized_attempts": Counter(anomalies[anomalies["status_code"] == 401]["ip"]),
        "bot_traffic": Counter(anomalies["user_agent"]),
        "referer_missing": Counter(anomalies[anomalies["referer"] == "-"]["ip"]),
        "large_response_sizes": large_response_sizes,  # Directly filtered from df
        "blocked_requests": Counter(anomalies[anomalies["status_code"] >= 400]["url"]),
        "suspicious_ip_activity": Counter(anomalies["ip"]),
    }


# Function to analyze resource utilization and identify overloaded resources
def find_overloaded_resources(logs, request_time_threshold=0.1, body_bytes_threshold=500):
    overloaded_resources = []
    
    for log in logs:
        request_time = log["request_time"]
        body_bytes_sent = log["body_bytes_sent"]
        resource = log["request"]["resource"]
        
        if request_time > request_time_threshold or body_bytes_sent > body_bytes_threshold:
            overloaded_resources.append({
                "resource": resource,
                "request_time": request_time,
                "body_bytes_sent": body_bytes_sent
            })
    
    return overloaded_resources


# Function to calculate connection metrics: Active and Dropped Connections
def calculate_connection_metrics(access_logs, timeout_threshold_minutes=5):
    active_connections = Counter()  # To store active connections per IP
    dropped_connections = Counter()  # To store dropped connections per IP
    connection_timestamps = {}  # To track the last timestamp of connections

    for log in access_logs:
        ip = log.get("ip")
        timestamp_str = log.get("timestamp")
        timestamp = datetime.strptime(timestamp_str, "%d/%b/%Y:%H:%M:%S")

        # Check for existing active connection (timeout logic)
        last_timestamp = connection_timestamps.get(ip)
        if last_timestamp:
            # If the difference between the current timestamp and the last timestamp exceeds the threshold, it is considered a dropped connection
            if (timestamp - last_timestamp) > timedelta(minutes=timeout_threshold_minutes):
                dropped_connections[ip] += 1

        # Update the connection timestamp
        connection_timestamps[ip] = timestamp

        # Count active connections for the current timestamp
        active_connections[ip] += 1

    # Assuming that if the connection is still active (has a timestamp but no drop event), it is still considered active
    active_connections_count = sum(active_connections.values())
    dropped_connections_count = sum(dropped_connections.values())

    return {
        "active_connections": active_connections_count,
        "dropped_connections": dropped_connections_count,
        "active_connections_by_ip": active_connections,
        "dropped_connections_by_ip": dropped_connections
    }


# Load data
access_logs = load_json(access_log_file)
aggregated_metrics = load_json(minute_metrics_file)

# Calculate metrics
traffic_metrics = calculate_traffic_metrics(access_logs, aggregated_metrics)
response_metrics = calculate_response_metrics(access_logs)
user_behavior_metrics = calculate_user_behavior_metrics(access_logs)
security_metrics = calculate_security_metrics(access_logs)
overloaded_resources = find_overloaded_resources(access_logs)
# Convert overloaded resources into a DataFrame for easier visualization
overloaded_df = pd.DataFrame(overloaded_resources)
connection_metrics = calculate_connection_metrics(access_logs)


st.markdown("""
    <style>
        .stMetric>div {
            background-color: #89CFF0;
            color: black;
            border-radius: 10px;
            padding: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
    </style>
""", unsafe_allow_html=True)

# Row 1: Summary Metrics
with st.container():
    st.markdown("## Traffic Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Max RPS", f"{traffic_metrics['max_rps']:.2f}")
    col2.metric("Min RPS", f"{traffic_metrics['min_rps']:.2f}")
    col3.metric("Unique Visitors", traffic_metrics["unique_visitors"])
    col4.metric("Avg Latency (ms)", f"{response_metrics['average_latency']:.2f}")

# Row 2: Traffic Visualizations
with st.container():
    st.markdown("### Traffic Distribution")
    col1, col2, col3 = st.columns(3)

    # Pie Chart for HTTP Methods
    http_methods_df = pd.DataFrame({
        "HTTP Method": list(traffic_metrics["http_methods"].keys()),
        "Count": list(traffic_metrics["http_methods"].values())
    })
    fig_http_methods = px.pie(http_methods_df, values="Count", names="HTTP Method", title="HTTP Methods Distribution")
    col1.plotly_chart(fig_http_methods, use_container_width=True)

    # Bar Chart for Status Codes
    status_data = pd.DataFrame({
        "Status Code": ["2xx", "3xx", "4xx", "5xx"],
        "Count": [
            response_metrics["status_code_distribution"].get(2, 0),
            response_metrics["status_code_distribution"].get(3, 0),
            response_metrics["status_code_distribution"].get(4, 0),
            response_metrics["status_code_distribution"].get(5, 0),
        ],
    })
    fig_status_codes = px.bar(status_data, x="Status Code", y="Count", title="HTTP Status Codes Distribution")
    col2.plotly_chart(fig_status_codes, use_container_width=True)

    # Bar Chart for Error and Redirect Rates
    rates_data = pd.DataFrame({
        "Metric": ["Error Rate (%)", "Redirect Rate (%)"],
        "Value": [response_metrics["error_rate"], response_metrics["redirect_rate"]]
    })
    fig_rates = px.bar(rates_data, x="Metric", y="Value", title="Error & Redirect Rates")
    col3.plotly_chart(fig_rates, use_container_width=True)

# Tabs for additional sections
st.markdown("### Detailed Insights")
tabs = st.tabs(["User Behavior", "Security Metrics","Resource Utilisation","Connection metrics"])

# Tab 1: User Behavior
with tabs[0]:
    st.markdown("#### Top URLs and User Agents")
    
    # Display Top 5 URLs
    top_urls_df = pd.DataFrame(user_behavior_metrics["top_urls"], columns=["URL", "Requests"])
    st.write("### Top 5 URLs")
    st.table(top_urls_df)

    # Display Browsers, Devices, and Bots information side by side
    st.write("### User Agent Information")
    col1, col2, col3 = st.columns(3)

    # Browsers Table
    browsers_df = pd.DataFrame(user_behavior_metrics["browsers"].items(), columns=["Browser", "Requests"])
    col1.write("#### Browsers")
    col1.table(browsers_df)

    # Devices Table
    devices_df = pd.DataFrame(user_behavior_metrics["devices"].items(), columns=["Device", "Requests"])
    col2.write("#### Devices")
    col2.table(devices_df)

    # Bots Table
    bots_df = pd.DataFrame(user_behavior_metrics["bots"].items(), columns=["Bot", "Requests"])
    col3.write("#### Bots")
    col3.table(bots_df)


    # Map visualization of Geolocation distribution (simple placeholder map)
    st.markdown("### Geolocation Distribution")
    # Here, using a basic map with random countries for visualization purposes.
    countries = ['USA', 'India', 'Germany', 'Brazil', 'Canada', 'Australia']
    country_data = {
        "Country": countries,
        "Requests": [300, 250, 150, 100, 200, 80]
    }
    geolocation_df = pd.DataFrame(country_data)

    # Create the geolocation map
    fig_map = px.scatter_geo(
        geolocation_df,
        locations="Country",
        locationmode="country names",
        size="Requests",
        title="Geolocation Map of Requests",
        template="plotly",
    )
    st.plotly_chart(fig_map, use_container_width=True)



# Tab 2: Security Metrics
with tabs[1]:
    st.markdown("## Security Insights")
    st.write("Analyze security-related trends, including suspicious activities, unusual patterns, and potential vulnerabilities.")

    # Sub-tabs for different security metrics
    security_tabs = st.tabs([
        "Suspicious IPs", "Unusual Requests", "High Latency", "Unauthorized Access", 
        "Bot Traffic", "Missing Referrers", "Large Response Sizes", "Blocked Requests", "Suspicious IP Activity"
    ])

    # Suspicious IPs - Enhanced Bar Chart
    with security_tabs[0]:  
        st.markdown("### Suspicious IPs (Frequent Failures)")
        st.write("These IPs have multiple failed requests (403, 401, 500 errors), which may indicate malicious activity.")

        # Extract IPs and their failure details (status codes)
        failure_data = []
        for log in access_logs:
            if log.get("status_code") in [403, 500, 503]:  # Filter for specific failure codes
                failure_data.append({
                    "IP Address": log.get("ip"),
                    "Status Code": log.get("status_code"),
                    "URL": log.get("request", {}).get("resource", ""),
                })
        
        # Convert to DataFrame
        failure_df = pd.DataFrame(failure_data)
        
        # Group by IP Address and Status Code to count failures
        if not failure_df.empty:
            failure_summary = failure_df.groupby(["IP Address", "Status Code"]).size().reset_index(name="Failure Count")
            
            # Create a bar chart
            fig_ip = px.bar(failure_summary, x="IP Address", y="Failure Count", color="Status Code",
                            color_continuous_scale="reds", title="Suspicious IPs (Frequent Failures)")
            fig_ip.update_layout(xaxis_tickangle=-45, xaxis_title="IP Address", yaxis_title="Failure Count")

            st.plotly_chart(fig_ip, use_container_width=True)
            
            # Display the detailed table
            st.write("Failure Details:")
            st.dataframe(failure_df.style.background_gradient(cmap="Reds"))
        else:
            st.warning("No suspicious IPs found.")

    # Unusual Request Patterns - Donut Chart
    with security_tabs[1]:  
        st.markdown("### Unusual Request Patterns")
        st.write("Endpoints with an abnormally high request frequency.")

        request_data = pd.DataFrame(list(security_metrics['unusual_request_patterns'].items()), columns=["Endpoint", "Request Count"])
        fig_request = px.pie(request_data, names="Endpoint", values="Request Count", hole=0.4, 
                             title="Unusual Request Distribution", color_discrete_sequence=px.colors.sequential.Blues)
        
        st.plotly_chart(fig_request, use_container_width=True)
        st.dataframe(request_data.style.background_gradient(cmap="Blues"))

    # High Latency Requests - Scatter Plot
    with security_tabs[2]:  
        st.markdown("### High Latency Requests")
        st.write("Requests that took significantly longer than expected.")

        latency_data = pd.DataFrame(security_metrics['high_latency_requests'])
    
        # Check if latency_data is not empty
        if not latency_data.empty:
            fig_latency = px.scatter(latency_data, x="url", y="response_time", size="response_time", color="response_time", 
                                 color_continuous_scale="viridis", title="High Latency Requests")
        
            st.plotly_chart(fig_latency, use_container_width=True)
            st.dataframe(latency_data.style.background_gradient(cmap="viridis"))
        else:
            st.warning("No high latency requests found.")
     
    # Unauthorized Authentication Attempts - Table View
    with security_tabs[3]:  
        st.markdown("### Unauthorized Authentication Attempts")
        st.write("Multiple failed login attempts from specific IPs, possibly indicating brute force attacks.")
        unauthorized_data = pd.DataFrame(list(security_metrics['unauthorized_attempts'].items()), 
                                         columns=["IP", "Attempt Count"])
        st.dataframe(unauthorized_data.style.background_gradient(cmap="Oranges"))

    # Bot Traffic - Donut Chart
    with security_tabs[4]:  
        st.markdown("### Bot Traffic (Detected from User Agents)")
        st.write("Requests that originated from automated bots or crawlers.")

        bot_data = pd.DataFrame(list(security_metrics['bot_traffic'].items()), columns=["User Agent", "Request Count"])
        fig_bot = px.pie(bot_data, names="User Agent", values="Request Count", hole=0.3, 
                         title="Bot Traffic Distribution", color_discrete_sequence=px.colors.sequential.Purp)

        st.plotly_chart(fig_bot, use_container_width=True)
        st.dataframe(bot_data.style.background_gradient(cmap="Purples"))

    # Missing Referrers - Grouped Bar Chart
    with security_tabs[5]:  
        st.markdown("### Requests Missing Referrers")
        st.write("Requests without a referrer header, often linked to automated scraping attempts.")

        referer_data = pd.DataFrame(list(security_metrics['referer_missing'].items()), columns=["IP Address", "Request Count"])
        fig_referer = px.bar(referer_data, x="IP Address", y="Request Count", color="Request Count", 
                             title="Requests Missing Referrers", color_continuous_scale="teal")
        
        st.plotly_chart(fig_referer, use_container_width=True)
        st.dataframe(referer_data.style.background_gradient(cmap="Greens"))

    # Large Response Sizes - Scatter Plot
    with security_tabs[6]:  
        st.markdown("### Large Response Sizes (Potential Data Exfiltration)")
        st.write("Requests returning unusually large responses, which could indicate data leaks or misconfigurations.")

        size_data = pd.DataFrame(security_metrics['large_response_sizes'])
    
        # Check if size_data is not empty
        if not size_data.empty:
            fig_size = px.scatter(size_data, x="url", y="response_size", size="response_size", color="response_size",
                              color_continuous_scale="reds", title="Large Response Sizes")
        
            st.plotly_chart(fig_size, use_container_width=True)
            st.dataframe(size_data.style.background_gradient(cmap="Reds"))
        else:
            st.warning("No large response sizes found.")

    # Blocked Requests - Bar Chart
    with security_tabs[7]:  
        st.markdown("### Blocked Requests")
        st.write("Requests that were blocked due to status codes >= 400 (e.g., 403, 404, 500).")

        blocked_data = pd.DataFrame(list(security_metrics['blocked_requests'].items()), columns=["URL", "Blocked Count"])
        fig_blocked = px.bar(blocked_data, x="URL", y="Blocked Count", color="Blocked Count",
                             color_continuous_scale="oranges", title="Blocked Requests")
        
        st.plotly_chart(fig_blocked, use_container_width=True)
        st.dataframe(blocked_data.style.background_gradient(cmap="Oranges"))

    # Suspicious IP Activity - Bar Chart
    with security_tabs[8]:  
        st.markdown("### Suspicious IP Activity")
        st.write("IP addresses with suspicious activity (e.g., multiple failed requests or anomalies).")

        suspicious_ip_data = pd.DataFrame(list(security_metrics['suspicious_ip_activity'].items()), columns=["IP Address", "Activity Count"])
        fig_suspicious_ip = px.bar(suspicious_ip_data, x="IP Address", y="Activity Count", color="Activity Count",
                                   color_continuous_scale="purples", title="Suspicious IP Activity")
        
        st.plotly_chart(fig_suspicious_ip, use_container_width=True)
        st.dataframe(suspicious_ip_data.style.background_gradient(cmap="Purples"))


# Tab 3: Server Resource Utilization
with tabs[2]:
    st.title("Server Resource Utilization Insights")
    
    # Display a table with overloaded resources
    st.write("### Overloaded Resources")
    st.table(overloaded_df)
    
    # Display a heatmap of request time vs body bytes sent for overloaded resources
    fig = px.density_heatmap(
        overloaded_df, 
        x="request_time", 
        y="body_bytes_sent", 
        title="Heatmap of Request Time vs Body Bytes Sent for Overloaded Resources",
        labels={"request_time": "Request Time (s)", "body_bytes_sent": "Body Bytes Sent (Bytes)"}
    )
    st.plotly_chart(fig, use_container_width=True)

    # Show a bar chart for resource counts (how many times each resource is overloaded)
    resource_counts = overloaded_df["resource"].value_counts().reset_index()
    resource_counts.columns = ["Resource", "Overload Count"]

    fig_bar = px.bar(resource_counts, x="Resource", y="Overload Count", title="Overload Count per Resource")
    st.plotly_chart(fig_bar, use_container_width=True)

    # Show a boxplot for request time distribution
    fig_box = px.box(overloaded_df, y="request_time", title="Distribution of Request Time for Overloaded Resources")
    st.plotly_chart(fig_box, use_container_width=True)

    # Show a boxplot for body bytes sent distribution
    fig_box_bytes = px.box(overloaded_df, y="body_bytes_sent", title="Distribution of Body Bytes Sent for Overloaded Resources")
    st.plotly_chart(fig_box_bytes, use_container_width=True)


# Tab 4: Connection Metrics Visualization
with tabs[3]:
    st.title("Active connections & Dropped connections")
    
     # Line chart for active connections over time
    st.write("### Active Connections Over Time")
    time_data = {
        "Timestamp": [],
        "Active Connections": []
    }
    for timestamp, active_count in connection_metrics["active_connections_by_ip"].items():
        time_data["Timestamp"].append(timestamp)
        time_data["Active Connections"].append(active_count)
    
    time_df = pd.DataFrame(time_data)
    fig_time = px.line(time_df, x="Timestamp", y="Active Connections", title="Active Connections Over Time")
    st.plotly_chart(fig_time, use_container_width=True)
    
    # Line chart for dropped connections over time
    st.write("### Dropped Connections Over Time")
    drop_time_data = {
        "Timestamp": [],
        "Dropped Connections": []
    }
    for timestamp, dropped_count in connection_metrics["dropped_connections_by_ip"].items():
        drop_time_data["Timestamp"].append(timestamp)
        drop_time_data["Dropped Connections"].append(dropped_count)
    
    drop_time_df = pd.DataFrame(drop_time_data)
    fig_drop_time = px.line(drop_time_df, x="Timestamp", y="Dropped Connections", title="Dropped Connections Over Time")
    st.plotly_chart(fig_drop_time, use_container_width=True)

    # Create two columns for the tables
    col1, col2 = st.columns(2)

    # Active Connections Table in the first column
    with col1:
        st.write("### Active Connections by IP")
        active_connections_df = pd.DataFrame(connection_metrics["active_connections_by_ip"].items(), columns=["IP Address", "Active Connections"])
        st.table(active_connections_df)

    # Dropped Connections Table in the second column
    with col2:
        st.write("### Dropped Connections by IP")
        dropped_connections_df = pd.DataFrame(connection_metrics["dropped_connections_by_ip"].items(), columns=["IP Address", "Dropped Connections"])
        st.table(dropped_connections_df)