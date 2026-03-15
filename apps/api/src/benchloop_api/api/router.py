from fastapi import APIRouter

from benchloop_api.api.routes.auth import router as auth_router
from benchloop_api.api.routes.configs import router as configs_router
from benchloop_api.api.routes.experiments import router as experiments_router
from benchloop_api.api.routes.health import router as health_router
from benchloop_api.api.routes.runs import history_router as run_history_router
from benchloop_api.api.routes.runs import router as runs_router
from benchloop_api.api.routes.settings import router as settings_router
from benchloop_api.api.routes.test_cases import router as test_cases_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(configs_router)
api_router.include_router(experiments_router)
api_router.include_router(health_router)
api_router.include_router(run_history_router)
api_router.include_router(runs_router)
api_router.include_router(settings_router)
api_router.include_router(test_cases_router)
