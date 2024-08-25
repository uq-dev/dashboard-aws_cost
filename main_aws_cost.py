import boto3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import schedule
import time
import argparse

def get_client(profile_name=None):
    """
    AWS CLIクライアントを作成する関数。
    :param profile_name: 使用するAWS CLIプロファイル名。デフォルトはNone。
    :return: boto3.client
    """
    if profile_name:
        session = boto3.Session(profile_name=profile_name)
        client = session.client('ce')
    else:
        client = boto3.client('ce')
    
    return client

def parse_arguments():
    """
    コマンドライン引数を解析する関数。
    :return: 引数の名前空間
    """
    parser = argparse.ArgumentParser(description='AWS Cost Explorer Dashboard')
    parser.add_argument('--profile', type=str, help='AWS CLI profile name to use')
    return parser.parse_args()

# 引数を解析
args = parse_arguments()
profile_name = args.profile

# AWSクライアントの設定
client = get_client(profile_name=profile_name)

# AWS料金情報の取得
def get_cost_and_usage(start_date, end_date, granularity):
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity=granularity,
        Metrics=['UnblendedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'}
        ]
    )
    return response

# データの変換
def transform_data(response):
    results = response['ResultsByTime']
    data = []
    
    for result in results:
        date = result['TimePeriod']['Start']
        for group in result['Groups']:
            service = group['Keys'][0]
            cost = float(group['Metrics']['UnblendedCost']['Amount'])
            data.append({'Date': date, 'Service': service, 'Cost': cost})
    
    df = pd.DataFrame(data)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # 0 USDの項目を除外
    df = df[df['Cost'] > 0]
    
    return df

# 日単位のグラフの描画
def plot_daily_cost(ax, df):
    if df.empty:
        print("No daily data to display.")
        return
    
    df_pivot = df.pivot_table(index='Date', columns='Service', values='Cost', aggfunc='sum').fillna(0)
    df_pivot = df_pivot.loc[:, (df_pivot != 0).any(axis=0)]
    
    df_pivot.plot(kind='bar', stacked=True, colormap='tab20', ax=ax)

    ax.set_title('AWS Daily Cost by Service (Stacked)')
    ax.set_xlabel('Date')
    ax.set_ylabel('Cost (USD)')
    
    # 横軸ラベルをyy-mm-dd形式に変更し、横書きに設定
    ax.xaxis.set_major_formatter(plt.FixedFormatter(df_pivot.index.strftime('%d')))
    ax.tick_params(axis='x', rotation=0)  # 横書き

    ax.legend(title='Service', bbox_to_anchor=(1.05, 1), loc='upper left')

# 月単位のグラフの描画
def plot_monthly_cost(ax, df):
    if df.empty:
        print("No monthly data to display.")
        return
    
    df_pivot = df.pivot_table(index='Date', columns='Service', values='Cost', aggfunc='sum').fillna(0)
    df_pivot = df_pivot.loc[:, (df_pivot != 0).any(axis=0)]
    
    df_pivot.plot(kind='bar', stacked=True, colormap='tab20', ax=ax)

    ax.set_title('AWS Monthly Cost by Service (Stacked)')
    ax.set_xlabel('Month')
    ax.set_ylabel('Cost (USD)')
    
    # 横軸ラベルをyyyy-mm形式に変更し、横書きに設定
    ax.xaxis.set_major_formatter(plt.FixedFormatter(df_pivot.index.strftime('%m')))
    ax.tick_params(axis='x', rotation=0)  # 横書き

    ax.legend(title='Service', bbox_to_anchor=(1.05, 1), loc='upper left')

# 1月分の予測
def predict_monthly_cost(df):
    daily_cost = df.groupby('Date').sum()['Cost'].mean()
    days_in_month = pd.Timestamp.today().days_in_month
    estimated_cost = daily_cost * days_in_month
    
    print(f"Estimated Monthly Cost: ${estimated_cost:.2f}")

# 自動更新のスケジュール設定
def job():
    today = datetime.today().strftime('%Y-%m-%d')
    six_months_ago = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')
    seven_days_ago = (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    # 日単位のデータ取得と変換
    daily_response = get_cost_and_usage(seven_days_ago, today, 'DAILY')
    daily_df = transform_data(daily_response)
    
    # 月単位のデータ取得と変換
    monthly_response = get_cost_and_usage(six_months_ago, today, 'MONTHLY')
    monthly_df = transform_data(monthly_response)
    
    # グラフの描画
    # DPIを設定（デフォルトは100）
    dpi = 100

    # インチへの変換
    width_inch = 683 / dpi
    height_inch = 768 / dpi

    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(width_inch, height_inch))
    
    # フィギュアの表示位置を指定
    # manager = plt.get_current_fig_manager()
    # manager.window.wm_geometry("+683+0")
    
    plot_daily_cost(axes[0], daily_df)
    plot_monthly_cost(axes[1], monthly_df)
    
    plt.tight_layout()
    plt.show()
    
    predict_monthly_cost(daily_df)

# job()

# 4時間ごとの自動更新
schedule.every(4).hours.do(job)

# プログラムの実行
if __name__ == "__main__":
   while True:
       schedule.run_pending()
       time.sleep(1)
