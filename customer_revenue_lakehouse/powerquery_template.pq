// Unexecuted Power Query M handoff. Set the local file path in Power BI Desktop.
let
    Source = Csv.Document(File.Contents("gold_monthly_country.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"month", type text}, {"Country", type text}, {"line_count", Int64.Type},
        {"purchase_invoices", Int64.Type}, {"known_customers", Int64.Type},
        {"unknown_customer_lines", Int64.Type}, {"gross_mills", Int64.Type},
        {"credit_mills", Int64.Type}, {"net_mills", Int64.Type}
    })
in
    Typed
