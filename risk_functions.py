"""Contains Functions Relating to Risk Assessment"""

from math import sqrt
import numpy as np
import pandas as pd
from enum import Enum
import logging

# Ugly but it allows keeping the same import statement across submodules and parent directories
try:
    from . import statistical_functions as StatisticalCalculations
    from .statistical_functions import Periods
except ImportError:
    import statistical_functions as StatisticalCalculations
    from statistical_functions import Periods



# TODO
def leverage_ratio(portfolio):
    """Takes Portfolio Data and Calculates the Leverage for all Assets"""

    # TODO Add some alert if outside of 1.5x - 3x


class PositionLimits():
    def __init__(
            self, 
            total_positions_df : pd.DataFrame,
            standard_deviation_df : pd.DataFrame,
            notional_exposure_per_contract_df : pd.DataFrame,
            open_interest_df : pd.DataFrame,
            IDM : float,
            instrument_weight : float,
            risk_target : float,
            average_forecast : int,
            max_forecast : int,
            max_leverage_ratio : float,
            capital : float,
            max_pct_of_open_interest : float,
            max_forecast_margin : float = 0.50):

        self.total_positions_df = total_positions_df.dropna()
        self.dates = self.total_positions_df.index.tolist()
        self.contract_names = self.total_positions_df.columns.tolist()

        self.risk_adjusted_positions : pd.DataFrame = pd.DataFrame(index=self.total_positions_df.index, columns=self.contract_names)
        
        self.standard_deviation_df = standard_deviation_df
        self.notional_exposure_per_contract_df = notional_exposure_per_contract_df
        self.open_interest_df = open_interest_df

        self.IDM = IDM
        self.instrument_weight = instrument_weight
        self.risk_target = risk_target
        self.average_forecast = average_forecast
        self.max_forecast = max_forecast
        self.max_leverage_ratio = max_leverage_ratio
        self.capital = capital
        self.max_pct_of_open_interest = max_pct_of_open_interest
        self.max_forecast_margin = max_forecast_margin

        self.set_risk_adjusted_positions()
    
    def set_risk_adjusted_positions(self):
        for date in self.dates:
            for contract in self.contract_names:
                self.risk_adjusted_positions.at[date, contract] = self.maximum_position(
                    contract,
                    self.total_positions_df.at[date, contract],
                    annualized_stddev=self.standard_deviation_df.at[date, contract],
                    notional_exposure_per_contract=self.notional_exposure_per_contract_df.at[date, contract],
                    open_interest=self.open_interest_df.at[date, contract])

    def get_risk_adjusted_positions(self):
        return self.risk_adjusted_positions

    def maximum_position(
            self,
            instrument_name,
            number_of_contracts,
            annualized_stddev,
            notional_exposure_per_contract,
            open_interest,) -> float:
        """Returns the lesser of the max position based on forecast, leverage, and open interest"""

        return min(
            self.maximum_position_forecast(instrument_name, number_of_contracts, notional_exposure_per_contract, annualized_stddev), 
            self.maximum_position_leverage(instrument_name, number_of_contracts, notional_exposure_per_contract), 
            self.maximum_position_open_interest(instrument_name, number_of_contracts, open_interest))

    def maximum_position_forecast(
            self,
            instrument_name : str,
            number_of_contracts : float,
            notional_exposure_per_contract : float,
            stddev : float) -> float:
        """
        Determines maximum position based on maximum forecast
        
        Parameters:
        ---
            number_of_contracts : float
                number of contracts forecasted by the algorithm
            scaled_forecast : float
                the scaled forecast created by the algorithm
            average_forecast : int
                average absolute forecast (Carver uses 10)
            max_forecast : int
                maximum absolute forecast (Carver uses 20)
            max_forecast_margin : float
                the margin around the max forecasted position acceptable 
                (Carver uses 50% so the position can exceed the max forecast by 50%)
        ---
        """

        #@                             zmax_forecast * capital * IDM * instrument_weight * risk_target
        #@ max_position_forecast   =   --------------------------------------------------------
        #@                             average_forecast * notional_exposure_per_contract * stddev

        max_forecast_ratio = self.max_forecast / self.average_forecast

        max_position_forecast = max_forecast_ratio * (self.capital * self.IDM * self.instrument_weight * self.risk_target) / (notional_exposure_per_contract * stddev)

        position_at_max_forecast = max_position_forecast * (1 + self.max_forecast_margin)

        max_position_of_forecast = min(position_at_max_forecast, number_of_contracts)

        if (max_position_of_forecast < number_of_contracts):
            logging.warning(f"Instrument: {instrument_name} - The maximum position at max forecast, {max_position_of_forecast}, is less than the current position, {number_of_contracts}.")

        return max_position_of_forecast

    def maximum_position_leverage(
            self,
            instrument_name : str,
            number_of_contracts : float,
            notional_exposure_per_contract : float) -> float:
        """
        Determines maximum position relative to maximum leverage
        
        Parameters:
        ---
            number_of_contracts : float
                number of contracts forecasted by the algorithm
            max_leverage_ratio : float
                the greatest level of leverage acceptable for any single position
            capital : float
                the amount of capital expected to be allocated to this position
            notional_exposure_per_contract : float 
                equals the multiplier * price * fx_rate
        ---
        """

        position_at_max_leverage = self.max_leverage_ratio * self.capital / notional_exposure_per_contract
    
        max_position_of_leverage = min(position_at_max_leverage, number_of_contracts)

        if (max_position_of_leverage < number_of_contracts):
            logging.warning(f"Instrument: {instrument_name} - The maximum position at max leverage, {max_position_of_leverage}, is less than the current position, {number_of_contracts}.")

        return max_position_of_leverage

    def maximum_position_open_interest(
            self,
            instrument_name : str,
            number_of_contracts : float,
            open_interest : int) -> float:
        """
        Determines maximum acceptable position in order to not exceed a certain % of open interest
        
        Parameters:
        ---
            number_of_contracts : float
                number of contracts forecasted by the algorithm
            open_interest : int
                the open interest for a given instrument
            max_open_interest : float
                the max acceptable % of open interest a position could be
        ---

        """

        max_position_of_interest = min(open_interest * self.max_pct_of_open_interest, number_of_contracts)

        if (max_position_of_interest < number_of_contracts):
            logging.warning(f"Instrument: {instrument_name} - The maximum position at max open interest, {max_position_of_interest}, is less than the current position, {number_of_contracts}.")

        return max_position_of_interest


class Volatility():
    # TODO: add calculations, change default value for minimum volatility
    def minimum_volatility(
            self,
            IDM : float,
            instrument_weight : float,
            risk_target : float,
            instrument_returns : list[float],
            maximum_leverage : float) -> bool:
        """
        Returns true if the returns for a given instrument meets a minimum level of volatility, false if not
        
        Parameters:
        ---
            IDM : float
                instrument diversification multiplier
            instrument_weight : float
                the weight of the instrument in the portfolio (capital allocated to the instrument / total capital)
            risk_target : float
                the target risk for the portfolio
            instrument_returns : list[float]
                the returns for a given instrument
            maximum_leverage : float
                the max acceptable leverage for a given instrument
        ---
        """

        minimum_volatility = (2 * IDM * instrument_weight * risk_target) / maximum_leverage

        standard_deviation = StatisticalCalculations.std(instrument_returns, annualize=True)

        if (standard_deviation < minimum_volatility):
            return False

        return True


class RiskOverlay():
    def __init__(
            self,
            total_positions_df : pd.DataFrame,
            position_weights : pd.DataFrame,
            position_percent_returns : pd.DataFrame,
            max_standard_deviation_risk : float = 0.30,
            max_jump_risk : float = 0.70,
            max_correlation_risk : float = 0.65,
            max_portfolio_leverage : int = 20) -> None:
        """
        Parameters:
        ---
            position_weights : pd.DataFrame
                each column should have the position weight for each ticker
                NOTE this is different from instrument weights:
                this weight is the notional exposure of the instrument divided by the total portfolio capital
            position_percent_returns : DataFrame
                each column are % returns for each ticker
            max_standard_deviation_risk : float
                max risk for the portfolio (should technically be 99th percentile of annualized risk)
        ---
        """

        self.total_positions_df : pd.DataFrame = total_positions_df.dropna()
        self.dates : list = self.total_positions_df.index.tolist()
        self.contract_names : list = self.total_positions_df.columns.tolist()

        self.position_weights : pd.DataFrame = position_weights
        self.position_percent_returns : pd.DataFrame = position_percent_returns

        self.max_standard_deviation_risk : float = max_standard_deviation_risk
        self.max_jump_risk : float = max_jump_risk
        self.max_correlation_risk : float = max_correlation_risk
        self.max_portfolio_leverage : int = max_portfolio_leverage

        self.rolling_stddevs : pd.DataFrame = pd.DataFrame(index=self.position_percent_returns.index, columns=self.contract_names)
        for contract in self.contract_names:
            self.rolling_stddevs[contract] = StatisticalCalculations.rolling_std(self.position_percent_returns[contract])


        self.correlation_matrices : list = []
        for idx, date in enumerate(self.dates):
            matrix_table = pd.read_csv(f"matrices/matrix{idx}.csv", header=None)
            matrix_array = np.array(matrix_table)
            self.correlation_matrices.append(matrix_array)

        self.risk_adjusted_positions : pd.DataFrame = pd.DataFrame(index=self.total_positions_df.index, columns=self.contract_names)

        self.set_risk_adjusted_positions()

    def set_risk_adjusted_positions(self):
        idx = 1
        for date in self.dates:
            std_risk = self.estimated_portfolio_risk_multiplier(idx)
            jump_risk = self.jump_risk_multiplier(idx)
            correlation_risk = self.correlation_risk_multiplier(idx)
            leverage_risk = self.leverage_risk_multiplier(idx)

            total_risk_multiplier = min(
                std_risk,
                jump_risk,
                correlation_risk,
                leverage_risk)

            for contract in self.contract_names:
                self.risk_adjusted_positions.at[date, contract] = self.total_positions_df.at[date, contract] * total_risk_multiplier

            idx += 1
            

    def get_risk_adjusted_positions(self):
        return self.risk_adjusted_positions

    #! Needs Optimization
    def estimated_portfolio_risk_multiplier(self, idx : int) -> float:
        portfolio_standard_deviation = StatisticalCalculations.portfolio_stddev(
            self.position_weights.iloc[:idx],
            self.position_percent_returns.iloc[:idx],
            self.rolling_stddevs.iloc[:idx],
            self.correlation_matrices[idx-1])

        standard_deviation_risk_multiplier = min(1, self.max_standard_deviation_risk / portfolio_standard_deviation)

        if (standard_deviation_risk_multiplier < 1):
            logging.warning(f"The estimated portfolio risk multiplier is {standard_deviation_risk_multiplier}, which is less than 1.")
        
        return standard_deviation_risk_multiplier


    #! Needs Optimization
    def jump_risk_multiplier(self, idx : int) -> float:
        stddev_lst = []

        for contract in self.contract_names:
            rolling_stddevs = self.rolling_stddevs.iloc[:idx][contract]
            stddev_lst.append(np.percentile(rolling_stddevs, 99))

        stddev_array = np.array(stddev_lst)

        corr_matrix = self.correlation_matrices[idx-1]

        covariance_matrix = np.dot(np.dot(np.diag(stddev_array), corr_matrix), np.diag(stddev_array))

        weights_lst : list = []

        # gets the weights for each instrument
        for contract in self.contract_names:
            contract_column_idx =  self.position_weights.columns.get_loc(contract)
            weights_lst.append(self.position_weights.iloc[idx, contract_column_idx])

        weights = np.array(weights_lst)

        weights_T = weights.transpose()

        radicand : float = np.dot(np.dot(weights, covariance_matrix), weights_T)

        jump_risk_multiplier = min(1, self.max_jump_risk / sqrt(radicand))

        if (jump_risk_multiplier < 1):
            logging.warning(f"The jump risk multiplier is {jump_risk_multiplier}, which is less than 1.")

        return jump_risk_multiplier
    

    def correlation_risk_multiplier(self, idx : int) -> float:
        risk_lst = []

        for contract in self.contract_names:
            # get the most recent value
            rolling_stddev = self.rolling_stddevs.iloc[:idx][contract]

            contract_column_idx = self.position_weights.columns.get_loc(contract)

            risk_lst.append(rolling_stddev * self.position_weights.iloc[idx, contract_column_idx])

        risk_lst = np.array(risk_lst)

        risk_lst = np.absolute(risk_lst)

        standard_deviation = np.sum(risk_lst)

        correlation_risk_multiplier = min(1, self.max_correlation_risk / standard_deviation)

        if (correlation_risk_multiplier < 1):
            logging.warning(f"The correlation risk multiplier is {correlation_risk_multiplier}, which is less than 1.")

        return correlation_risk_multiplier
    

    def leverage_risk_multiplier(self, idx : int) -> float:
        weights_lst : list = []

        # gets the weights for each instrument
        for contract in self.contract_names:
            contract_column_idx = self.position_weights.columns.get_loc(contract)
            weights_lst.append(self.position_weights.iloc[idx, contract_column_idx])

        weights = np.array(weights_lst)

        absolute_weights = np.absolute(weights)

        leverage = np.sum(absolute_weights)

        leverage_risk_multiplier = min(1, self.max_portfolio_leverage / leverage)

        if (leverage_risk_multiplier < 1):
            logging.warning(f"The leverage risk multiplier is {leverage_risk_multiplier}, which is less than 1.")

        return leverage_risk_multiplier


class MarginLevels(float, Enum):
    """Margin Level Concern and Upper Limit"""
    NO_ACTION = 0.0
    ALERT = 0.50
    TAKE_ACTION = 0.60


class Margins():
    # TODO: Create function to determine margin of a given portfolio
    def margin_level(self, portfolio) -> float:
        margin : float = 0.75

        return margin

    # TODO: Create scaling reduction function
    def scale_portfolio(self, portfolio, scaleback : float):
        """Returns a portfolio that has been reduced to the scaleback fraction of the original value"""

        return portfolio

    # TODO 
    def margin_action(self, portfolio):
        margin = self.margin_level(portfolio)

        if (margin < MarginLevels.ALERT):
            return MarginLevels.NO_ACTION
        
        if (margin < MarginLevels.TAKE_ACTION):
            return MarginLevels.ALERT
        
        # at this point the Margin Level is high enough to require scaling back to the ALERT level
        scaleback : float = MarginLevels.ALERT / margin

        return self.scale_portfolio(portfolio, scaleback)
