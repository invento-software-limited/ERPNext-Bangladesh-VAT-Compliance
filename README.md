### 🚀 Bangladesh Vat Compliance

A Frappe app for managing VAT compliance in Bangladesh.

### ✨ Features

#### 📄 Reports
- **Mushak 6.3**: VAT Challan.
- **Purchase Register - Mushak 6.1**: Purchase register report.
- **Sales Register - Mushak 6.2**: Sales register report.
- **Purchase Sales Ledger For Trader**: Ledger for traders.
- **Sales VAT Management**: Manage Sales VAT.
- **VDS Management**: VAT Deduction at Source management.
- **Supplier Mushak 6.3**: Supplier VAT Challan.

#### 📦 Doctypes
- **VAT Deduction Certificate**: Manage VAT deduction certificates.
- **Document Attachment**: Attach documents for compliance.

### 🎥 Video Tutorial

Check out our tutorial video to get started:
[Watch Tutorial](https://youtu.be/gw2UJtEmlkE?si=ALzICQIHz4wyzuKi)

### 📚 Documentation

Detailed documentation is available in the `docs` folder:

- **[Product Overview](docs/product_overview.md)**:
    - **Target Audience**: Traders, Retailers, Manufacturers, and Service Providers.
    - **Key Features**:
        - **Statutory Forms**: Mushak 6.3 (Tax Invoice), 6.1 (Purchase Register), 6.2 (Sales Register), 6.2.1 (Purchase-Sales Ledger), 6.6 (VDS Certificate).
        - **Compliance Management**: VDS Management, Sales VAT Management, Treasury Deposits, TIN & BIN Verification.

- **[User Guide](docs/user_guide.md)**:
    - **Getting Started**: Setup Item Tax Templates and Items.
    - **Sales Workflow**: Create compliant Sales Invoices with vehicle details and manage VAT collection.
    - **Purchase Workflow**: Record purchases and manage VAT Deduction at Source (VDS).
    - **Compliance Reports**:
        - **Sales VAT Management**: Monitor Sales VAT liability and upload VDS certificates.
        - **VDS Management**: Manage VDS from purchases and treasury deposits.
        - **VAT Payment Page**: Consolidate and pay outstanding VAT liabilities.
        - **Registers & Ledgers**: Access Mushak 6.1, 6.2, and 6.2.1 reports.

- **[Smart VAT Challan](docs/smart_vat_challan.md)**:
    - **Integration**: Secure integration with NBR Smart VAT APIs.
    - **Features**: Automated challan generation, retailer & branch registration, and advanced analytics.
    - **Reports**: VAT Invoice Monitor, Branch-wise Sales, and Service-type Sales.

### 🔄 Workflows

- **Sales**: Create compliant Sales Invoices with vehicle details and manage VAT collection.
- **Purchase**: Record purchases and manage VAT Deduction at Source (VDS).
- **Compliance**: Automatically generate Mushak 6.3, 6.1, 6.2, and other required reports.

### 🛠️ Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app vat_compliance
```

### 🤝 Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/vat_compliance
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### 📄 License

mit
