# -*- coding: utf-8 -*-
"""
Below is a re-implementation of Royston and Parmar spline models,

Reference: Flexible parametric proportional-hazards and proportional-odds models for censored survival data, with application to prognostic modelling and estimation of treatment e􏰎ects
"""
from autograd import numpy as np
from lifelines.datasets import load_lymph_node
from lifelines.fitters import ParametricRegressionFitter
from autograd.scipy.special import expit
import pandas as pd
from lifelines import CoxPHFitter
from matplotlib import pyplot as plt


class SplineFitter:
    _scipy_fit_method = "SLSQP"
    _scipy_fit_options = {"ftol": 1e-12}

    @staticmethod
    def relu(x):
        return np.maximum(0, x)

    def basis(self, x, knot, min_knot, max_knot):
        lambda_ = (max_knot - knot) / (max_knot - min_knot)
        return self.relu(x - knot) ** 3 - (lambda_ * self.relu(x - min_knot) ** 3 + (1 - lambda_) * self.relu(x - max_knot) ** 3)


class PHSplineFitter(SplineFitter, ParametricRegressionFitter):
    """
    Proportional Hazard model

    References
    ------------
    Royston, P., & Parmar, M. K. B. (2002). Flexible parametric proportional-hazards and proportional-odds models for censored survival data, with application to prognostic modelling and estimation of treatment effects. Statistics in Medicine, 21(15), 2175–2197. doi:10.1002/sim.1203
    """

    _fitted_parameter_names = ["beta_", "phi1_", "phi2_"]
    _KNOWN_MODEL = True

    KNOTS = [0.1972, 1.769, 6.728]

    def _create_initial_point(self, Ts, E, entries, weights, Xs):
        return {"beta_": np.zeros(len(Xs["beta_"].columns)), "phi1_": np.array([0.1]), "phi2_": np.array([0.0])}

    def _cumulative_hazard(self, params, T, Xs):
        exp_Xbeta = np.exp(np.dot(Xs["beta_"], params["beta_"]))
        lT = np.log(T)
        return exp_Xbeta * np.exp(
            params["phi1_"] * lT
            + params["phi2_"] * self.basis(lT, np.log(self.KNOTS[1]), np.log(self.KNOTS[0]), np.log(self.KNOTS[-1]))
        )


class POSplineFitter(SplineFitter, ParametricRegressionFitter):
    """
    Proportional Odds model

    References
    ------------
    Royston, P., & Parmar, M. K. B. (2002). Flexible parametric proportional-hazards and proportional-odds models for censored survival data, with application to prognostic modelling and estimation of treatment effects. Statistics in Medicine, 21(15), 2175–2197. doi:10.1002/sim.1203
    """

    _fitted_parameter_names = ["beta_", "phi1_", "phi2_"]
    _KNOWN_MODEL = True

    KNOTS = [0.1972, 1.769, 6.728]

    def _cumulative_hazard(self, params, T, Xs):
        Xbeta = np.dot(Xs["beta_"], params["beta_"])
        lT = np.log(T)

        return np.log1p(
            np.exp(
                Xbeta
                + (
                    params["phi1_"] * lT
                    + params["phi2_"] * self.basis(lT, np.log(self.KNOTS[1]), np.log(self.KNOTS[0]), np.log(self.KNOTS[-1]))
                )
            )
        )


class AltWeibullFitter(ParametricRegressionFitter):
    """
    Alternative parameterization of Weibull Model
    """

    _fitted_parameter_names = ["beta_", "phi1_"]
    _scipy_fit_method = "SLSQP"
    _KNOWN_MODEL = True

    def _cumulative_hazard(self, params, T, Xs):
        exp_Xbeta = np.exp(np.dot(Xs["beta_"], params["beta_"]))
        lT = np.log(T)
        return exp_Xbeta * np.exp(params["phi1_"] * lT)


df = load_lymph_node()

df["T"] = df["rectime"] / 365.0
df["E"] = df["censrec"]

# see paper for where these come from
df["linear_predictor"] = (
    1.79 * (df["age"] / 50) ** (-2)
    - 8.02 * (df["age"] / 50) ** (-0.5)
    + 0.5 * (df["grade"] >= 2).astype(int)
    - 1.98 * np.exp(-0.12 * df["nodes"])
    - 0.058 * (df["prog_recp"] + 1) ** 0.5
    - 0.394 * df["hormone"]
)
df["binned_lp"] = pd.qcut(df["linear_predictor"], np.linspace(0, 1, 4), labels=["good", "medium", "poor"])

# these values look right. Differences could be due to handling ties vs Stata
cph = CoxPHFitter().fit(df, "T", "E", formula="binned_lp").print_summary(columns=["coef"])

print()
# check PH(1) Weibull model (different parameterization from lifelines)
regressors = {"beta_": "binned_lp", "phi1_": "1"}
waf = AltWeibullFitter().fit(df, "T", "E", regressors=regressors).print_summary(columns=["coef"])

print()
# Check PH(2) model
regressors = {"beta_": "binned_lp", "phi1_": "1", "phi2_": "1"}
phf = PHSplineFitter()
phf.fit(df, "T", "E", regressors=regressors).print_summary(columns=["coef"])


print()
print()
# Check PO(2) mode
regressors = {"beta_": "binned_lp", "phi1_": "1", "phi2_": "1"}
pof = POSplineFitter()
pof.fit(df, "T", "E", regressors=regressors).print_summary(columns=["coef"])

print()
# looks like figure 2 from paper.
pof.predict_hazard(pd.DataFrame({"binned_lp": ["poor", "medium", "good"]})).plot()
plt.show()
