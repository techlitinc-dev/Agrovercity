from typing import Literal

from pydantic import BaseModel, Field


class TreeArticle(BaseModel):
    id: str
    title: str
    category: str
    author: str
    readTime: str
    summary: str
    fullContent: str
    benefits: list[str]
    publishedDate: str


class NgoOrganization(BaseModel):
    id: str
    name: str
    focusArea: str
    location: str
    contactPhone: str
    email: str
    treesPlantedCount: int
    rating: float
    servicesOffered: list[str]
    providesFreeSaplings: bool
    websiteUrl: str


class SaplingRequestIn(BaseModel):
    treeType: Literal["timber", "biofuel", "fruit", "bamboo"]
    count: int = Field(ge=1, le=500)


class BiofuelTree(BaseModel):
    id: str
    name: str
    botanicalName: str
    oilContentPercent: float
    gestationPeriod: str
    expectedReturnPerAcre: str
    suitability: str
    uses: list[str]
    buyerMarket: str
    subsidyScheme: str


class TreeCareGuide(BaseModel):
    id: str
    title: str
    stepNumber: int
    stage: str
    instructions: str
    wateringRule: str
    fertilizerSchedule: str
    pestProtection: str
