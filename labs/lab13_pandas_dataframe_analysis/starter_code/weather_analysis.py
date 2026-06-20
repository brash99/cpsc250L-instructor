import pandas as pd
import matplotlib.pyplot as plt


def load_weather_data(filename):
    # TODO: load the data from csv file
    # TODO: return a Pandas dataframe
    pass


def print_summary(df):
    # TODO: print summary statistics
    # TODO: extract the mean temperature and print it
    pass

def add_celsius(df):
    # TODO: add columns for temperatures converted to Celsius
    # TODO: return modified dataframe
    pass


def clean_temperature_range(df, t_low_cut, t_high_cut):
    # TODO: remove days where T_low < t_low_cut or T_high > t_high_cut
    # TODO: return modified dataframe
    pass


def plot_temperatures(df):
    # TODO: plot both high and low temperatures on the same graph
    pass


def main():

    filename = "../data/weather_june.csv"

    dataframe = load_weather_data(filename)

    dataframe = add_celsius(dataframe)

    T_low_cut = 19.0
    T_high_cut = 31.0
    dataframe = clean_temperature_range(dataframe, T_low_cut, T_high_cut)

    print_summary(dataframe)

    plot_temperatures(dataframe)

main()
