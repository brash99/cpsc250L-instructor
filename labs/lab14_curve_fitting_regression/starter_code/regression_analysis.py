import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_data(filename):
    # TODO: load data in filename into pandas dataframe and return it
    pass

def fit_polyfit(df):
    # TODO: fit a first order polynomial and return slope and intercept
    pass

def fit_statsmodel(df):
    # TODO: carry out a linear regression fit and return the results object
    pass

def fit_curve_fit(df):
    # TODO: fit a first order polynonial and return slope, int, dslope, dint
    pass

def predict(x, slope, intercept):
    # TODO: return y-values based on x, slope, intercept
    pass

def fitfunc(x, *param):
    # TODO: write a linear fit function for use with curve_fit
    pass


def main():

    # Get the file into a dataframe
    filename = "../data/study_scores.csv"
    df = load_data(filename)

    # calculate the slope and intercept of the best fit line
    slope, intercept = fit_polyfit(df)
    print("Best fit: y = {slope:.4f}x + {intercept:.4f}".format(slope=slope, intercept=intercept))
    print('-------------------------------------')

    # get the best fit line (as data for plotting)
    y_fit = predict(df['hours'], slope, intercept)

    # make the plot
    plt.figure()
    plt.plot(df['hours'], df['score'], 'o', label='Exam Score')
    plt.plot(df['hours'], y_fit, 'r-', label=f'Linear Fit - y = {slope:.4f}x + {intercept:.4f}')
    plt.title('Computer Science 250 Final Exam Score')
    plt.xlabel("Study Hours")
    plt.ylabel("Exam Score")
    plt.legend()
    plt.show()

    # Use statsmodels for comparison!
    results = fit_statsmodel(df)
    print(results.summary())
    print('---------------------------------------')

    # Now, use curve_fit for comparison to statsmodels errors
    slope_cf, intercept_cf, dslope_cf, dintercept_cf  = fit_curve_fit(df)
    print(f"Curve Fit: y = ({slope_cf:.4f} +/- {dslope_cf:.3f})x + ({intercept_cf:.4f} +/- {dintercept_cf:.3f})")

main()
