from fastapi import FastAPI
from pydantic import BaseModel
import os
from .core import run_discovery, build_prd, plan_oag, execute_plan

app = FastAPI(title="Plugah Orchestrator API", version="0.1.0")

class OrchestrateReq(BaseModel):
    problem: str
    budget: float
    policy: str | None = None
    model_hint: str | None = None
    mock: bool = False

class PlanReq(BaseModel):
    problem: str
    budget: float
    answers: list[str]
    policy: str | None = None
    model_hint: str | None = None
    mock: bool = False

@app.post("/orchestrate")
async def orchestrate(req: OrchestrateReq):
    if req.mock:
        os.environ["PLUGAH_MODE"] = "mock"
    questions = await run_discovery(req.problem, req.budget, model_hint=req.model_hint, policy=req.policy)
    return {"questions": questions}

@app.post("/plan")
async def plan(req: PlanReq):
    if req.mock:
        os.environ["PLUGAH_MODE"] = "mock"
    prd = await build_prd(req.answers, req.problem, req.budget, model_hint=req.model_hint, policy=req.policy)
    oag = await plan_oag(prd, req.budget, model_hint=req.model_hint, policy=req.policy)
    return {"prd": prd, "oag": oag}

@app.post("/execute")
async def execute():
    results = await execute_plan()
    return results

def serve():
    import uvicorn
    uvicorn.run("app.web:app", host="127.0.0.1", port=8000, reload=True)
