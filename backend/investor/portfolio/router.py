"""Portfolio analytics endpoints."""

from fastapi import APIRouter, Query

from investor.portfolio.performance import PerformanceRequest, portfolio_performance
from investor.portfolio.prediction import prediction_history
from investor.portfolio.regression import RegressionRequest, regression_deviations
from investor.portfolio.service import PortfolioRequest, portfolio
from investor.portfolio.volatility import asset_volatility, portfolio_volatility

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.post("/portfolio/analytics")
def portfolio_analytics(request: PortfolioRequest):
    return portfolio(request)


@router.post("/portfolio/regression")
def portfolio_regression(request: RegressionRequest):
    return regression_deviations(request)


@router.get("/assets/{asset_id}/volatility")
def get_asset_volatility(asset_id: str, years: int = Query(default=3, ge=1, le=20)):
    return asset_volatility(asset_id, years)


@router.post("/portfolio/volatility")
def get_portfolio_volatility(request: PortfolioRequest):
    return portfolio_volatility(request)


@router.post("/portfolio/performance")
def get_portfolio_performance(request: PerformanceRequest):
    return portfolio_performance(request)


@router.post("/portfolio/optimize")
def optimize_portfolio(request: PerformanceRequest):
    return portfolio_performance(request, optimize=True)


@router.post("/portfolio/prediction")
def get_portfolio_prediction(request: PortfolioRequest):
    return prediction_history(request)
