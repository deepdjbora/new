import numpy as np
from numba import njit

@njit
def ema_numba(close, length):
    out = np.full_like(close, np.nan)
    
    if len(close) <= length:
        return out
    
    alpha = 2 / (length + 1)
    ema = np.mean(close[:length])  # Initialize with SMA
    out[length-1] = ema
    
    for i in range(length, len(close)):
        ema = alpha * close[i] + (1 - alpha) * ema
        out[i] = ema
    
    return np.round(out, 2)

import numpy as np
from numba import njit

@njit
def jma_numba(src, length, phase, power):
    out = np.full_like(src, np.nan)
    
    if len(src) <= length:
        return out
    
    phaseRatio = 1.5 + phase / 100 if -100 <= phase <= 100 else (0.5 if phase < -100 else 2.5)
    beta = 0.45 * (length - 1) / (0.45 * (length - 1) + 2)
    alpha = np.power(beta, power)
    
    e0 = e1 = e2 = jma = 0.0
    
    for i in range(len(src)):
        if i == 0:
            e0 = src[i]
            e1 = 0.0
            e2 = 0.0
            jma = 0.0
        else:
            e0 = (1 - alpha) * src[i] + alpha * e0
            e1 = (src[i] - e0) * (1 - beta) + beta * e1
            e2 = (e0 + phaseRatio * e1 - jma) * np.power(1 - alpha, 2) + np.power(alpha, 2) * e2
            jma = e2 + jma
            
            # Reset values if they become too large or unstable
            if np.abs(jma) > 1e10:
                e0 = e1 = e2 = jma = 0.0
        
        if i >= length - 1:
            out[i] = np.round(jma, 2)
    
    return out

import numpy as np
from numba import njit

@njit
def alma_numba(series, length, offset, sigma):
    out = np.full_like(series, np.nan)
    
    if len(series) < length:
        return out
    
    for i in range(length - 1, len(series)):
        numerator = 0.0
        denominator = 0.0
        m = offset * (length - 1)
        s = length / sigma
        for j in range(length):
            weight = np.exp(-((j - m) ** 2) / (2 * s * s))
            numerator += weight * series[i - length + 1 + j]
            denominator += weight
        out[i] = round(numerator / denominator, 2)
    
    return out


@njit
def rsi_trail_numba(open, high, low, close, rsi_lower=45, rsi_upper=55, ma_length=20, ma_offset=0.85, ma_sigma=6):
    ohlc4 = (open + high + low + close) / 4
    ma = alma_numba(ohlc4, ma_length, ma_offset, ma_sigma)
    atr = atr_numba(high, low, close, 7)
    upper_bound = ma + (rsi_upper - 50) / 10 * atr
    lower_bound = ma - (50 - rsi_lower) / 10 * atr
    
    signal = np.zeros_like(close, dtype=np.float64)
    is_bullish = np.zeros_like(close, dtype=np.bool_)
    is_bearish = np.zeros_like(close, dtype=np.bool_)
    
    signal[:ma_length] = np.nan  # Set initial values to NaN
        
    for i in range(ma_length, len(close)):
        if ohlc4[i] > upper_bound[i]:
            if not is_bullish[i-1]:
                signal[i] = 1  # Bullish crossover
            is_bullish[i] = True
            is_bearish[i] = False
        elif close[i] < lower_bound[i]:
            if not is_bearish[i-1]:
                signal[i] = -1  # Bearish crossunder
            is_bullish[i] = False
            is_bearish[i] = True
        else:
            signal[i] = 0  # Neutral
            is_bullish[i] = is_bullish[i-1]
            is_bearish[i] = is_bearish[i-1]
    
    return signal, is_bullish, is_bearish

@njit
def atr_numba(high, low, close, length):
    true_range = np.zeros_like(close)
    atr = np.full_like(close, np.nan)
    
    for i in range(1, len(close)):
        true_range[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    
    for i in range(length, len(close)):
        if i == length:
            atr[i] = np.mean(true_range[:length])
        else:
            atr[i] = (atr[i - 1] * (length - 1) + true_range[i]) / length
    
    return atr


@njit
def chandelier_exit_numba(open, high, low, close, length=2, mult=1):
    atr = atr_numba(high, low, close, length) * mult
    
    long_stop = np.full_like(close, np.nan)
    short_stop = np.full_like(close, np.nan)
    direction = np.zeros_like(close)
    
    for i in range(length, len(close)):
        highest = np.max(close[i-length+1:i+1])
        lowest = np.min(close[i-length+1:i+1])
        
        long_stop[i] = highest - atr[i]
        short_stop[i] = lowest + atr[i]
        
        if i > length:
            long_stop[i] = max(long_stop[i], long_stop[i-1]) if close[i-1] > long_stop[i-1] else long_stop[i]
            short_stop[i] = min(short_stop[i], short_stop[i-1]) if close[i-1] < short_stop[i-1] else short_stop[i]
        
        if close[i] > short_stop[i-1]:
            direction[i] = 1
        elif close[i] < long_stop[i-1]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1] if i > 0 else 0
    
    return long_stop, short_stop, direction

@njit()
def custom_round(x, decimals=2):
    """
    Custom rounding function for Numba (nopython mode).
    """
    multiplier = 10 ** decimals
    return np.floor(x * multiplier + 0.5) / multiplier

@njit()
def calculate_average_height_range(high, low, length):

    last_10_high = high[-length:]
    last_10_low = low[-length:]

    # Directly access the last element of high as a float
    current_candle_high = float(high[-1]) 
    current_candle_low = float(low[-1])

    # Calculate the height of each candle (high - low)
    avg_candle_heights = last_10_high - last_10_low

    average_height = np.mean(avg_candle_heights)

    current_candle_hight = current_candle_high - current_candle_low

    # Round to 2 decimal places
    average_height = custom_round(average_height)
    current_candle_hight = custom_round(current_candle_hight)
    
    return average_height, current_candle_hight
    

@njit
def calculate_current_bar_length(high, low):
    # Calculate the length of the current bar
    current_bar_length = high[-1] - low[-1]
    return current_bar_length

def test_indicators():
    print("Indicator functions loaded successfully!")