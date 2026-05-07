# - Libraries -
import pandas as pd
import numpy as np

FEATURE_COLUMNS = [
    # Raw behavior
    'status',               # Kondisi endpoint (UP/DOWN)
    'response_time_ms',     # Response time (ms)
    'http_status_code',     # Kode http dari hasil respons

    # Temporal
    'hour',                 # Terjadinya jam request untuk mengetahui pola harian
    'day',                  # Menunjukkan hari dalam minggu untuk menangkap pola mingguan
    'is_weekend',           # Apakah request terjadi di weekend (potensi traffic berbeda)

    # Statistics    
    'rolling_z_score',      # Seberapa jauh response time saat ini menyimpang dari rata-rata historis
    'rt_percentile',        # Posisi response time saat ini dibandingkan distribusi historis
    'rt_rolling_std',       # Apakah response time stabil dalam periode pendek (standard deviation)

    # Sequence
    'fail_diff',            # Menunjukkan perubahan status kegagalan dibandingkan request sebelumnya untuk mendeteksi lonjakan error.
    'rt_diff',              # Selisih rt sekarang dengan rt sebelumnya
    'rt_drift',             # Membandingkan rata-rata jangka pendek dan panjang untuk mendeteksi pergeseran performa.

    # Service
    'is_monolith',          # Apakah endpoint monolith / microservice
    'service_median_rt',    # Median rt untuk setiap service
    'rt_relative'           # Rt relatif terhadap baseline service untuk memahami deviasi performa.
]

def _prepare_base(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df['checked_at'] = pd.to_datetime(df['checked_at'], errors='coerce')
    df = df.dropna(subset=['checked_at'])

    df = df.sort_values(['id_aplikasi', 'id_service', 'checked_at']).reset_index(drop=True)

    df['id_service'] = df['id_service'].fillna('monolithic').astype(str)
    df['http_status_code'] = df['http_status_code'].fillna(200).astype(int)
    df['response_time_ms'] = df['response_time_ms'].fillna(-1).astype(int)

    df['status'] = df['status'].map({'UP': 1, 'DOWN': 0})
    df['status_fail'] = 1 - df['status']

    return df

def _temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    df['hour'] = df['checked_at'].dt.hour
    df['day'] = df['checked_at'].dt.dayofweek
    df['is_weekend'] = df['day'].isin([5, 6]).astype(int)
    return df

def _statistical_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby('id_service')

    rolling_mean = group['response_time_ms'].transform(lambda x: x.rolling(5, min_periods=1).mean())
    rolling_std = group['response_time_ms'].transform(lambda x: x.rolling(5, min_periods=1).std())

    df['rolling_z_score'] = (df['response_time_ms'] - rolling_mean) / (rolling_std + 1e-5)
    df['rt_percentile'] = group['response_time_ms'].transform(lambda x: x.rank(pct=True))
    df['rt_rolling_std'] = rolling_std.fillna(0)

    return df

def _sequence_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby('id_service')

    df['fail_diff'] = group['status_fail'].diff().fillna(0)
    df['rt_diff'] = group['response_time_ms'].diff().fillna(0)

    short_mean = group['response_time_ms'].transform(lambda x: x.rolling(5, min_periods=1).mean())
    long_mean = group['response_time_ms'].transform(lambda x: x.rolling(20, min_periods=1).mean())

    df['rt_drift'] = short_mean - long_mean

    return df

def _service_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby('id_service')

    df['is_monolith'] = (df['id_service'] == 'monolithic').astype(int)
    df['service_median_rt'] = group['response_time_ms'].transform('median')
    df['rt_relative'] = df['response_time_ms'] / (df['service_median_rt'] + 1e-5)

    return df

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = _prepare_base(df)
    original_df = df.copy()
    
    df = _temporal_features(df)
    df = _statistical_features(df)
    df = _sequence_features(df)
    df = _service_features(df)

    feature_df = df[FEATURE_COLUMNS].fillna(0)
    
    return original_df, feature_df