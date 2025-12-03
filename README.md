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

### 📚 Documentation

For detailed instructions on how to use the app, including setup, sales and purchase workflows, and report generation, please refer to the **[User Guide](docs/user_guide.md)**.

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
