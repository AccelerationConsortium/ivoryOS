# IvoryOS Example Gallery

This page contains example projects showing how to integrate your SDL with IvoryOS.


## 🧩 Abstract Integrations

### **Abstract SDL**
**Description:** Demonstrates multi-instance SDL integration — runnable without hardware.  
**Related Link(s):** [link](https://demo.ivoryos.ai)  
**Author / Contributor:** Ivory Zhang (Hein Group, UBC)

---

### **Branin Function**
**Description:** Demonstrates optimization using the Branin function — runnable without hardware.  
**Related Link(s):** [link](#)  
**Author / Contributor:** Ivory Zhang (Hein Group, UBC)  

---


## ⚙️ Platform Integrations

### **ADC example**
**Description:** Antibody Drug Conjugation (ADC) platform for automated conjugation workflows.  
**Related Link(s):** [ADC Automation](https://gitlab.com/heingroup/adc-automation)  
**Author / Contributor:** Liam Robert (Hein Lab, UBC)  
**Image:** ![ADC example]()  

---

### **PurPOSE**
**Description:** Purification Platform Optimizing Solubility-based Experimentation (PurPOSE).  
**Related Link(s):** [PurPOSE](https://gitlab.com/heingroup/purpose)  
**Author / Contributor:** Noah Depner, Rebekah Greenwood, Maria Politi (Hein Lab, UBC)  
**Image:** ![PurPOSE]()  

---

### **Flow chem**
**Description:** Flow chemistry optimizer adapted for IvoryOS (single-objective EDBO).  
**Related Link(s):** [Flow Chem](https://github.com/jiayu423/Autonomous-flow-optimizer)  
**Author / Contributor:** Jiayu Zhang, Jacob Jessiman  (Hein Lab, UBC)  
**Image:** ![Flow Chem]()  

---

### **LLE**
**Description:** Liquid-Liquid Extraction (LLE) platform (work-in-progress).  
**Related Link(s):** [Automated LLE (not available now)](https://gitlab.com/heingroup/automated-lle)  
**Author / Contributor:** Maria Politi  (Hein Lab, UBC)  
**Image:** ![LLE]()  

---

### **Solubility**
**Description:** Solubility platform at Telescope Innovations Corp.  
**Related Link(s):** —  
**Author / Contributor:** Veronica Lai, Ryan Corkery (Telescope Innovations)  
**Image:** ![Solubility]()  

---

### **Derivatization sampling**
**Description:** Derivatization sampling setup using DirectInject and Sielc autosampler.  
**Related Link(s):** [Sielc Dompser](https://gitlab.com/heingroup/sielc_dompser)  
**Author / Contributor:** Junliang Liu, Yusuke Sato  (Telescope Innovations)  
**Image:** ![Derivatization]()  

---

### **Minimalee**
**Description:** Electrochemical dipping robot   
**Related Link(s):** [Minimalee (not available now)](https://gitlab.com/heingroup/minimalee-control)  
**Author / Contributor:** Matt Reish  (Hein Lab, UBC)     
**Image:** ![Minimalee]()  

---



[//]: # (---------- add more use cases above -------------------)





## 🤝 Contributing

We welcome contributions that showcase your use cases of IvoryOS. 

### Create a card for your example in the relevant section:
- **Abstract Integrations** (hardware-free examples)
- **Platform Integrations** (hardware or robotic setups)

```markdown
### **Your demo or robot name**
**Description:** A short description   
**Related Link(s):** [link](your repo link)  
**Author / Contributor:** names  (affiliation)     
**Image:** ![image](your image link)  

---
```

### Adding more details
- **Option 1:** Create a folder under the `community/examples/` directory with a descriptive name:
```
examples/
└── my_lab_example/
    ├── my_lab_example.py        # Your SDL class and ivoryos.run()
    ├── README.md                # Description (see template below)
    ├── requirements.txt         # Optional dependencies
   ```
- **Option 2:** Link to your own repository


## Other Contribution Routes

You can also contribute by:

🧠 Improving the IvoryOS core

🧪 Sharing your application of IvoryOS 

🔌 Adding Instrument SDKs — wrappers or connectors for lab hardware.

🧩 Adding plugin pages for data analysis, monitoring, etc.

📖 Improving docs and tutorials — clear examples benefit the entire community.

💬 Opening issues or discussions — suggest new features or share feedback.