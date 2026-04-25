# IAIso v5.0 + LangChain Integration
```python
from langchain.chains import LLMChain
from iaiso.integrations.langchain import IAIsoPressureWrapper
from iaiso.core.magnification import apply_magnification

# Wrap with IAIso containment
safe_chain = IAIsoPressureWrapper(
    chain=LLMChain(llm=llm, prompt=prompt),
    pressure_threshold=0.85,
    enable_magnification=True
)

# Execution uses magnification if enabled in l.env
result = safe_chain.invoke({"input": user_query})
```
